# -*- coding: utf-8 -*-
"""Phase 14 — 小规模训练结果分析:
- 用 best.pt 对 val 100 图做详细评估: 每类 P/R/mAP + 混淆矩阵 (保存 runs/)
- 预测样例: 对含 blind_road 的 val 图推理并保存标注图 (保存 runs/)
- 输出: docs/training_analysis_stats.json
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 沙箱适配 (同 Phase 13)
os.environ["YOLO_CONFIG_DIR"] = r"D:\BlindRoadMonitor\.yolo_config"
os.environ["MPLCONFIGDIR"] = r"D:\BlindRoadMonitor\.yolo_config\mpl"
os.makedirs(r"D:\BlindRoadMonitor\.yolo_config\mpl", exist_ok=True)

import glob
from concurrent.futures import ThreadPoolExecutor

import ultralytics.data.dataset as _uds


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

BEST = r"D:\BlindRoadMonitor\runs\smoke_test\yolov8n_smoke_b16\weights\best.pt"
YAML = r"D:\BlindRoadMonitor\datasets\smoke_test\data.yaml"
OUT_DIR = r"D:\BlindRoadMonitor\runs\smoke_test\analysis"
OUT_JSON = r"D:\BlindRoadMonitor\docs\training_analysis_stats.json"
os.makedirs(OUT_DIR, exist_ok=True)

m = YOLO(BEST)

# 1) val 详细评估 (每类指标, plots=False 先取数字)
val_res = m.val(data=YAML, imgsz=640, batch=16, device=0, plots=False, verbose=False, workers=0)
stats = {
    "val_total": {
        "images": int(val_res.nt_per_image.shape[0]) if hasattr(val_res, "nt_per_image") else 100,
        "instances": int(val_res.nt_per_class.sum()) if hasattr(val_res, "nt_per_class") else None,
        "mAP50": round(float(val_res.box.map50), 4),
        "mAP50_95": round(float(val_res.box.map), 4),
        "precision": round(float(val_res.box.mp), 4),
        "recall": round(float(val_res.box.mr), 4),
    },
    "per_class": {},
}
names = val_res.names
for i, name in names.items():
    i = int(i)
    try:
        stats["per_class"][name] = {
            "P": round(float(val_res.box.p[i]), 4),
            "R": round(float(val_res.box.r[i]), 4),
            "mAP50": round(float(val_res.box.ap50[i]), 4),
            "mAP50_95": round(float(val_res.box.ap[i]), 4),
        }
    except Exception as e:
        stats["per_class"][name] = {"err": str(e)}

# 2) 混淆矩阵 (需要 plots)
print("[1] 生成混淆矩阵图 (val plots)...")
m.val(data=YAML, imgsz=640, batch=16, device=0, plots=True, verbose=False, project=OUT_DIR, name="val_plots", exist_ok=True, workers=0)

# 3) 预测样例: 找含 blind_road 的 val 图
print("[2] 生成预测样例图...")
SMOKE_VAL = r"D:\BlindRoadMonitor\datasets\smoke_test\images\val"
blind_imgs = []
for fn in sorted(os.listdir(SMOKE_VAL)):
    if not fn.endswith(".jpg"):
        continue
    lp = os.path.join(r"D:\BlindRoadMonitor\datasets\smoke_test\labels\val", fn[:-4] + ".txt")
    if not os.path.exists(lp):
        continue
    with open(lp, encoding="utf-8") as f:
        if any(l.split()[0] == "0" for l in f if l.strip()):
            blind_imgs.append(os.path.join(SMOKE_VAL, fn))
print(f"    含盲道 val 图: {len(blind_imgs)} 张, 选前 {min(6, len(blind_imgs))} 张")

samples_saved = []
res = m.predict(
    source=blind_imgs[:6] if blind_imgs else sorted(os.path.join(SMOKE_VAL, f) for f in os.listdir(SMOKE_VAL))[:6],
    imgsz=640,
    conf=0.1,
    device=0,
    save=True,
    project=OUT_DIR,
    name="predict_samples",
    exist_ok=True,
    workers=0,
)
# 找保存的预测图
pred_dir = os.path.join(OUT_DIR, "predict_samples")
if os.path.isdir(pred_dir):
    for f in sorted(os.listdir(pred_dir)):
        if f.lower().endswith((".jpg", ".png")):
            samples_saved.append(os.path.join(pred_dir, f).replace("\\", "/"))
stats["prediction_samples"] = samples_saved[:12]
stats["cm_dir"] = os.path.join(OUT_DIR, "val_plots").replace("\\", "/")

with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)
print("[3] 完成 ->", OUT_JSON)
print(json.dumps(stats, ensure_ascii=False, indent=2))
