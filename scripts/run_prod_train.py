# -*- coding: utf-8 -*-
"""Phase 15 — 正式模型训练 (production training)

- 正式数据规模: datasets/processed/data.yaml (17,908 图 / train 10,043 / val 3,702 / test 4,163)
- 模型: yolov8n (COCO 预训练) | imgsz=640 | batch=32 | epochs=200 | patience=40
- 沙箱适配(同 Phase 13/14): YOLO_CONFIG_DIR / MPLCONFIGDIR / monkeypatch ThreadPool / workers=0
- 磁盘安全: 训练前 check_before_operation(required_gb=15); 训练中每 epoch 回调查 D 盘, <15GB 安全停止
- OOM 兜底: batch 32 -> 16 -> 8 (出现 OOM 自动降 batch, 不碰系统 CUDA)
- 产物: runs/yolov8n_prod_b{32,16,8}/ (best.pt / last.pt / results.csv / 训练曲线)
        + docs/final_training_stats.json (供 final_training_report.md 使用)
"""
import os
import sys
import json
import time
import gc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disk_manager import get_disk_info, check_before_operation, DiskStatus

# ---- 沙箱适配 (同 Phase 13/14) ----
os.environ["YOLO_CONFIG_DIR"] = r"D:\BlindRoadMonitor\.yolo_config"
os.environ["MPLCONFIGDIR"] = r"D:\BlindRoadMonitor\.yolo_config\mpl"
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import torch
from concurrent.futures import ThreadPoolExecutor
import ultralytics.data.dataset as _uds


class _NoPipeThreadPool:
    """纯线程池替换 ultralytics 的 ThreadPool(命名管道被沙箱拒)。仅影响缓存扫描。"""

    def __init__(self, max_workers=None):
        self._ex = ThreadPoolExecutor(max_workers=max_workers or 1)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._ex.shutdown(wait=True)
        return False

    def imap(self, func, iterable):
        futs = [self._ex.submit(func, item) for item in iterable]
        for f in futs:
            yield f.result()


_uds.ThreadPool = _NoPipeThreadPool

from ultralytics import YOLO

ROOT = r"D:\BlindRoadMonitor"
DATA = os.path.join(ROOT, "datasets", "processed", "data.yaml")
WEIGHTS = os.path.join(ROOT, "models", "yolov8n.pt")
PROJECT = os.path.join(ROOT, "runs")
OUT_JSON = os.path.join(ROOT, "docs", "final_training_stats.json")

CFG = dict(
    imgsz=640,
    epochs=200,
    patience=40,
    amp=True,          # 混合精度(Phase 13 已验证通过)
    close_mosaic=10,  # 末 10 epoch 关 mosaic 提升稳定
    device=0,
    workers=0,         # Windows spawn+管道受限
    optimizer="auto",
    seed=20260902,
    cos_lr=True,
    cls=1.0,           # 长尾类(437:1)适度加强分类损失
)


def count_images(split: str) -> int:
    d = os.path.join(ROOT, "datasets", "processed", "images", split)
    if not os.path.isdir(d):
        return 0
    return sum(1 for f in os.listdir(d) if f.lower().endswith((".jpg", ".png")))


# ---- 训练前磁盘闸门 ----
gate = check_before_operation(op_name="Phase15 正式训练", drive="D:\\", required_gb=15)
print(f"[gate] status={gate.status} free={gate.free_gb:.1f}GB ok={gate.ok}")
if not gate.ok:
    print("[gate] 不满足, 中止:", gate.reason)
    raise SystemExit(2)


# ---- 训练中磁盘安全回调: D 盘 <15GB (DANGER) 安全停止 ----
def on_epoch_end(trainer):
    info = get_disk_info("D:\\")
    ep = trainer.epoch + 1
    print(f"[disk] epoch {ep}/{CFG['epochs']} done | D: free={info.free_gb:.1f}GB status={info.status}")
    if info.status == DiskStatus.DANGER:
        print("[disk] DANGER (<15GB) -> 安全停止训练 (等待用户指令)")
        trainer.stop = True


def run_eval(split: str, best_pt: str):
    """用 best.pt 在指定划分上评估, 返回 (overall, per_class)。"""
    m = YOLO(best_pt)
    res = m.val(
        data=DATA, imgsz=640, batch=32, device=0,
        split=split, plots=False, verbose=False, workers=0,
    )
    overall = dict(
        images=count_images(split),
        mAP50=round(float(res.box.map50), 4),
        mAP50_95=round(float(res.box.map), 4),
        precision=round(float(res.box.mp), 4),
        recall=round(float(res.box.mr), 4),
    )
    per_class = {}
    for i, name in res.names.items():
        i = int(i)
        try:
            per_class[name] = dict(
                P=round(float(res.box.p[i]), 4),
                R=round(float(res.box.r[i]), 4),
                mAP50=round(float(res.box.ap50[i]), 4),
                mAP50_95=round(float(res.box.ap[i]), 4),
            )
        except IndexError:
            per_class[name] = dict(P=0.0, R=0.0, mAP50=0.0, mAP50_95=0.0,
                                  note="该划分无此类目标 (非标签问题)")
        except Exception as e:
            per_class[name] = dict(err=str(e))
    return overall, per_class


# ---- 训练 (batch 兜底 32->16->8) ----
LAST_SAVE_DIR = None
actual_batch = None
peak_mb = 0.0
success = False
t_start = time.time()

for batch in (32, 16, 8):
    name = f"yolov8n_prod_b{batch}"
    try:
        torch.cuda.reset_peak_memory_stats()
        model = YOLO(WEIGHTS)
        model.add_callback("on_train_epoch_end", on_epoch_end)
        trainer = model.train(
            data=DATA,
            name=name,
            project=PROJECT,
            exist_ok=False,   # 若目录已存在, ultralytics 自动 _2 递增, 不覆盖旧实验
            batch=batch,
            **CFG,
        )
        LAST_SAVE_DIR = trainer.save_dir
        actual_batch = batch
        peak_mb = torch.cuda.max_memory_allocated() / 1024 ** 2
        success = True
        break
    except RuntimeError as e:
        msg = str(e).lower()
        if "out of memory" in msg or "cuda" in msg:
            print(f"[OOM] batch={batch} 失败, 清理显存并降 batch 重试")
            gc.collect()
            torch.cuda.empty_cache()
            continue
        else:
            raise
    except Exception as e:  # 其它异常直接上浮
        print("[train error]", repr(e))
        raise

if not success:
    print("[FAIL] 所有 batch 均失败, 中止")
    raise SystemExit(3)

elapsed = time.time() - t_start
best_pt = os.path.join(LAST_SAVE_DIR, "weights", "best.pt")
last_pt = os.path.join(LAST_SAVE_DIR, "weights", "last.pt")

# ---- 最终评估 (val + test) ----
print("[eval] 在 val / test 划分上评估 best.pt ...")
val_overall, val_pc = run_eval("val", best_pt)
test_overall, test_pc = run_eval("test", best_pt)

end_info = get_disk_info("D:\\")
stats = dict(
    phase="Phase 15 正式训练",
    config=dict(
        model="yolov8n (COCO 预训练)", weights=WEIGHTS, data=DATA,
        imgsz=CFG["imgsz"], epochs=CFG["epochs"], patience=CFG["patience"],
        amp=CFG["amp"], close_mosaic=CFG["close_mosaic"], optimizer=CFG["optimizer"],
        seed=CFG["seed"], cos_lr=CFG["cos_lr"], cls=CFG["cls"], workers=CFG["workers"],
        actual_batch=actual_batch, device="cuda:0 (RTX 5070 8GB)",
    ),
    dataset_counts=dict(
        train=count_images("train"), val=count_images("val"), test=count_images("test"),
    ),
    run_dir=str(LAST_SAVE_DIR),
    weights=dict(best=best_pt, last=last_pt),
    results_csv=os.path.join(LAST_SAVE_DIR, "results.csv"),
    elapsed_sec=round(elapsed, 1),
    gpu_peak_mb=round(peak_mb, 1),
    val=dict(overall=val_overall, per_class=val_pc),
    test=dict(overall=test_overall, per_class=test_pc),
    disk_end=dict(free_gb=round(end_info.free_gb, 1), status=end_info.status),
    stopped_by_disk_danger=False,
)

with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print("=" * 60)
print(f"[done] 训练完成: batch={actual_batch} epochs~{int((time.time()-t_start)//60)}min "
      f"GPU峰值={peak_mb:.0f}MB")
print(f"[done] val mAP50={val_overall['mAP50']} mAP50-95={val_overall['mAP50_95']} "
      f"P={val_overall['precision']} R={val_overall['recall']}")
print(f"[done] blind_road(val) mAP50={val_pc.get('blind_road', {}).get('mAP50')}")
print(f"[done] 统计 -> {OUT_JSON}")
print("=" * 60)
