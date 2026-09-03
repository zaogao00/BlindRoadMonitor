# -*- coding: utf-8 -*-
"""Phase 15 收尾: 不重训, 仅用已训好的 best.pt 复评 val/test, 生成干净的 final_training_stats.json。

- 训练早已完成 (runs/yolov8n_prod_b32/best.pt + last.pt + results.csv 齐全)
- 修复原 run_prod_train.py 末尾 json.dump(WindowsPath) 崩溃的问题: 这里所有路径都用 str()
- 输出: docs/final_training_stats.json (供 final_training_report.md 使用)
"""
import os
import sys
import json
import csv

ROOT = r"D:\BlindRoadMonitor"
DATA = os.path.join(ROOT, "datasets", "processed", "data.yaml")
BEST_PT = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "weights", "best.pt")
LAST_PT = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "weights", "last.pt")
RESULTS_CSV = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "results.csv")
OUT_JSON = os.path.join(ROOT, "docs", "final_training_stats.json")
RUN_DIR = os.path.join(ROOT, "runs", "yolov8n_prod_b32")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disk_manager import get_disk_info

# ---- 沙箱适配 (同 Phase 13/14) ----
os.environ["YOLO_CONFIG_DIR"] = r"D:\BlindRoadMonitor\.yolo_config"
os.environ["MPLCONFIGDIR"] = r"D:\BlindRoadMonitor\.yolo_config\mpl"
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

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
        futs = [self._ex.submit(func, item) for item in iterable]
        for f in futs:
            yield f.result()


_uds.ThreadPool = _NoPipeThreadPool

from ultralytics import YOLO


def count_images(split: str) -> int:
    d = os.path.join(ROOT, "datasets", "processed", "images", split)
    if not os.path.isdir(d):
        return 0
    return sum(1 for f in os.listdir(d) if f.lower().endswith((".jpg", ".png")))


def run_eval(split: str, best_pt: str):
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


def read_results_csv(path: str):
    """读取 results.csv, 返回 (rows, best_epoch_idx)。best 按 fitness=0.1*mAP50+0.9*mAP50-95。"""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    best_idx = 0
    best_fit = -1.0
    for idx, row in enumerate(rows):
        try:
            m50 = float(row.get("metrics/mAP_0.5", 0) or 0)
            m5095 = float(row.get("metrics/mAP_0.5:0.95", 0) or 0)
        except ValueError:
            continue
        fit = 0.1 * m50 + 0.9 * m5095
        if fit > best_fit:
            best_fit = fit
            best_idx = idx
    return rows, best_idx


def main():
    print(f"[finalize] 复评 best.pt on val/test ... best={BEST_PT}")
    val_overall, val_pc = run_eval("val", BEST_PT)
    test_overall, test_pc = run_eval("test", BEST_PT)

    rows, best_idx = read_results_csv(RESULTS_CSV)
    last_row = rows[-1]
    best_row = rows[best_idx]
    print(f"[finalize] epochs={len(rows)} best_epoch_idx={best_idx} (0-based)")

    def fnum(row, key):
        try:
            return round(float(row.get(key, 0) or 0), 4)
        except ValueError:
            return None

    per_epoch = dict(
        total_epochs=len(rows),
        best_epoch=int(best_idx) + 1,
        best=dict(
            epoch=int(best_idx) + 1,
            box_loss=fnum(best_row, "train/box_loss"),
            cls_loss=fnum(best_row, "train/cls_loss"),
            dfl_loss=fnum(best_row, "train/dfl_loss"),
            mAP50=fnum(best_row, "metrics/mAP_0.5"),
            mAP50_95=fnum(best_row, "metrics/mAP_0.5:0.95"),
            precision=fnum(best_row, "metrics/precision"),
            recall=fnum(best_row, "metrics/recall"),
        ),
        final=dict(
            epoch=len(rows),
            box_loss=fnum(last_row, "train/box_loss"),
            cls_loss=fnum(last_row, "train/cls_loss"),
            dfl_loss=fnum(last_row, "train/dfl_loss"),
            mAP50=fnum(last_row, "metrics/mAP_0.5"),
            mAP50_95=fnum(last_row, "metrics/mAP_0.5:0.95"),
            precision=fnum(last_row, "metrics/precision"),
            recall=fnum(last_row, "metrics/recall"),
        ),
    )

    end_info = get_disk_info("D:\\")
    stats = dict(
        phase="Phase 15 正式训练",
        status="completed",
        config=dict(
            model="yolov8n (COCO 预训练)",
            weights=str(BEST_PT),
            data=str(DATA),
            imgsz=640, epochs=200, patience=40,
            amp=True, close_mosaic=10, optimizer="auto",
            seed=20260902, cos_lr=True, cls=1.0,
            workers=0, actual_batch=32, device="cuda:0 (RTX 5070 8GB)",
        ),
        dataset_counts=dict(
            train=count_images("train"), val=count_images("val"), test=count_images("test"),
        ),
        run_dir=str(RUN_DIR),
        weights=dict(best=str(BEST_PT), last=str(LAST_PT)),
        results_csv=str(RESULTS_CSV),
        per_epoch=per_epoch,
        val=dict(overall=val_overall, per_class=val_pc),
        test=dict(overall=test_overall, per_class=test_pc),
        disk_end=dict(free_gb=round(end_info.free_gb, 1), status=end_info.status),
        stopped_by_disk_danger=False,
    )

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"[done] val  mAP50={val_overall['mAP50']} mAP50-95={val_overall['mAP50_95']} "
          f"P={val_overall['precision']} R={val_overall['recall']}")
    print(f"[done] test mAP50={test_overall['mAP50']} mAP50-95={test_overall['mAP50_95']} "
          f"P={test_overall['precision']} R={test_overall['recall']}")
    print(f"[done] blind_road(val) mAP50={val_pc.get('blind_road', {}).get('mAP50')} "
          f"mAP50-95={val_pc.get('blind_road', {}).get('mAP50_95')}")
    print(f"[done] 统计 -> {OUT_JSON}")
    print("=" * 60)


if __name__ == "__main__":
    main()
