# -*- coding: utf-8 -*-
"""Phase 13 — smoke test 训练运行器 (记录时间/显存/loss/mAP 到 JSON)"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 沙箱环境适配: Ultralytics 默认把字体/设置写入 %APPDATA% (不可写)。
# 用 YOLO_CONFIG_DIR 重定向到项目内可写目录 (.yolo_config/Ultralytics, 含预置 Arial.ttf)。
os.environ["YOLO_CONFIG_DIR"] = r"D:\BlindRoadMonitor\.yolo_config"
os.environ["MPLCONFIGDIR"] = r"D:\BlindRoadMonitor\.yolo_config\mpl"
os.makedirs(r"D:\BlindRoadMonitor\.yolo_config\mpl", exist_ok=True)

import json
import time

import torch
from ultralytics import YOLO

# ---- 沙箱适配 2: ultralytics 缓存扫描用 multiprocessing.pool.ThreadPool,
# 其内部 SimpleQueue 需创建命名管道, 被沙箱拒绝 ([WinError 5])。
# 用纯线程池 (concurrent.futures, 无管道) 包装替换, 仅影响标签缓存扫描, 不改训练逻辑。
try:
    import ultralytics.data.dataset as _uds
    from concurrent.futures import ThreadPoolExecutor

    class _NoPipeThreadPool:
        def __init__(self, max_workers=None):
            self._ex = ThreadPoolExecutor(max_workers=max_workers or 1)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._ex.shutdown(wait=True)
            return False

        def imap(self, func, iterable):
            # ThreadPool.imap 是惰性有序迭代; futures 完成后按提交序收集
            futs = [self._ex.submit(func, item) for item in iterable]
            for f in futs:
                yield f.result()

    _uds.ThreadPool = _NoPipeThreadPool
    print("[PATCH] ultralytics ThreadPool -> 纯线程 (无命名管道)")
except Exception as _e:
    print(f"[WARN] ThreadPool patch 失败: {_e}")

YAML = r"D:\BlindRoadMonitor\datasets\smoke_test\data.yaml"
OUT_JSON = r"D:\BlindRoadMonitor\docs\training_smoke_test_stats.json"

start = time.time()
m = YOLO(r"D:\BlindRoadMonitor\models\yolov8n.pt")

# 记录 GPU 初始显存
torch.cuda.reset_peak_memory_stats()
gpu_init = torch.cuda.memory_allocated() / 1024**2

# batch: 先用 16 (RTX 5070 8GB + AMP, n 模型), 若 OOM 由外部降级处理
batch = int(os.environ.get("SMOKE_BATCH", "16"))

print(f"[TRAIN] yaml={YAML} batch={batch} imgsz=640 amp=True epochs=10", flush=True)
try:
    results = m.train(
        data=YAML,
        epochs=10,
        imgsz=640,
        batch=batch,
        amp=True,
        project=r"D:\BlindRoadMonitor\runs\smoke_test",
        name=f"yolov8n_smoke_b{batch}",
        exist_ok=True,
        seed=20260902,
        workers=0,
        verbose=False,
        plots=False,
    )
    elapsed = time.time() - start
    gpu_peak = torch.cuda.max_memory_allocated() / 1024**2
    stats = {
        "ok": True,
        "batch": batch,
        "elapsed_sec": round(elapsed, 1),
        "gpu_init_mb": round(gpu_init, 1),
        "gpu_peak_mb": round(gpu_peak, 1),
        "train_dir": str(m.trainer.save_dir),
    }
    # 从 last.pt / best.pt 的 trainer metrics 取 loss/mAP
    if m.trainer is not None:
        metrics = m.trainer.metrics if hasattr(m.trainer, "metrics") else None
        t = m.trainer
        stats["final"] = {
            "epoch": getattr(t, "epoch", None),
            "lr": getattr(t, "lr", None),
            "train_loss_box": getattr(t, "train_loss_box", None),
            "train_loss_cls": getattr(t, "train_loss_cls", None),
            "train_loss_dfl": getattr(t, "train_loss_dfl", None),
        }
        try:
            import csv
            rp = os.path.join(str(m.trainer.save_dir), "results.csv")
            if os.path.exists(rp):
                with open(rp, encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                if rows:
                    last = rows[-1]
                    stats["csv_last_row"] = {k: v for k, v in last.items()}
                    stats["csv_first_row"] = {k: v for k, v in rows[0].items()}
        except Exception as e:
            stats["csv_err"] = str(e)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"[DONE] elapsed={elapsed:.0f}s gpu_peak={gpu_peak:.0f}MB -> {OUT_JSON}", flush=True)
except Exception as e:
    elapsed = time.time() - start
    gpu_peak = torch.cuda.max_memory_allocated() / 1024**2
    err = str(e)
    print(f"[FAIL] {err[:500]}", flush=True)
    # OOM 检测
    is_oom = "out of memory" in err.lower() or "CUDA out of memory" in err.lower()
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "ok": False,
            "oom": is_oom,
            "batch": batch,
            "elapsed_sec": round(elapsed, 1),
            "gpu_peak_mb": round(gpu_peak, 1),
            "error": err[:800],
        }, f, ensure_ascii=False, indent=2)
    sys.exit(1 if is_oom else 2)
