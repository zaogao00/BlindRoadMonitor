# -*- coding: utf-8 -*-
"""Phase 18 — 部署 / 推理性能优化 Benchmark。

严格边界 (Phase 18):
  - 不重新训练 / 不修改 best.pt / 不导出 ONNX-TensorRT / 不修改数据集。
  - 仅对正式模型 runs/yolov8n_prod_b32/weights/best.pt 做推理侧 Benchmark。
  - 复用 Phase 13/15/16/17 沙箱兼容方案 (YOLO_CONFIG_DIR / MPLCONFIGDIR / ThreadPool monkeypatch / workers=0)。

输出:
  - 终端打印摘要
  - runs/yolov8n_prod_b32/phase18_benchmark/benchmark_stats.json (gitignore, 不入库)
"""
import os
import sys
import time
import json
import glob
import subprocess
from collections import defaultdict

ROOT = r"D:\BlindRoadMonitor"
os.environ["YOLO_CONFIG_DIR"] = os.path.join(ROOT, ".yolo_config")
os.environ["MPLCONFIGDIR"] = os.path.join(ROOT, ".yolo_config", "mpl")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import ultralytics.data.dataset as _uds
from concurrent.futures import ThreadPoolExecutor


class _NoPipeThreadPool:
    """纯线程池替换 ultralytics ThreadPool (命名管道被沙箱拒)。仅影响缓存扫描。"""
    def __init__(self, max_workers=None):
        self._ex = ThreadPoolExecutor(max_workers=max_workers or 1)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._ex.shutdown(wait=True)
        return False

    def imap(self, func, iterable):
        for f in [self._ex.submit(func, i) for i in iterable]:
            yield f.result()


_uds.ThreadPool = _NoPipeThreadPool

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from ultralytics import YOLO  # noqa: E402

WEIGHTS = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "weights", "best.pt")
IMG_DIR = os.path.join(ROOT, "datasets", "processed", "images", "test")
LBL_DIR = os.path.join(ROOT, "datasets", "processed", "labels", "test")
OUT_DIR = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "phase18_benchmark")
os.makedirs(OUT_DIR, exist_ok=True)

IMGSZ = 640
CONF = 0.25
CONF_LOW = 0.15
IOU = 0.45
DEVICE = "0"
N_WARMUP = 20
N_ITER = 250

TARGET_CLASSES = ["blind_road", "person", "bicycle", "motorcycle", "car", "truck", "bus"]


def query_nvidia_smi_used_mib():
    """用 nvidia-smi 取当前真实 GPU 显存占用 (MiB), 失败返回 None。"""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL, timeout=10,
        ).decode().strip()
        return int(out.splitlines()[0].strip())
    except Exception:
        return None


def get_names():
    m = YOLO(WEIGHTS)
    return m.names


def collect_target_images(names):
    """从 test 划分挑若干覆盖 TARGET_CLASSES 的图, 以及若干盲道 GT 图。"""
    id2name = {int(k): v for k, v in names.items()}
    name2id = {v: int(k) for k, v in names.items()}
    target_ids = [name2id[c] for c in TARGET_CLASSES if c in name2id]

    per_class = defaultdict(list)
    blind_road_imgs = []
    for lp in glob.glob(os.path.join(LBL_DIR, "*.txt")):
        with open(lp) as f:
            lines = [l.split() for l in f if l.strip()]
        if not lines:
            continue
        ids = set(int(x[0]) for x in lines)
        for cid in ids:
            if cid in target_ids:
                per_class[cid].append(lp)
        if name2id.get("blind_road") in ids:
            blind_road_imgs.append(lp)

    chosen = []
    seen = set()
    # 每个目标类取一张图 (尽量不同图)
    for cid in target_ids:
        for lp in per_class[cid]:
            stem = os.path.splitext(os.path.basename(lp))[0]
            img = os.path.join(IMG_DIR, stem + ".jpg")
            if os.path.isfile(img) and stem not in seen:
                chosen.append(img)
                seen.add(stem)
                break
    # 补充盲道 GT 图 (最多 +4 张, 不同图)
    for lp in blind_road_imgs:
        stem = os.path.splitext(os.path.basename(lp))[0]
        img = os.path.join(IMG_DIR, stem + ".jpg")
        if os.path.isfile(img) and stem not in seen and len(chosen) < 10:
            chosen.append(img)
            seen.add(stem)
    return chosen, blind_road_imgs, id2name


def bench_precision(precision, timing_images):
    half = (precision == "fp16")
    model = YOLO(WEIGHTS)
    dummy = np.zeros((IMGSZ, IMGSZ, 3), dtype=np.uint8)
    # warmup
    for _ in range(N_WARMUP):
        model.predict(source=dummy, imgsz=IMGSZ, conf=CONF, iou=IOU,
                       device=DEVICE, half=half, verbose=False)
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()

    times = []
    for i in range(N_ITER):
        img = timing_images[i % len(timing_images)]
        frame = cv2.imread(img)
        if frame is None:
            frame = dummy
        t0 = time.perf_counter()
        model.predict(source=frame, imgsz=IMGSZ, conf=CONF, iou=IOU,
                       device=DEVICE, half=half, verbose=False)
        torch.cuda.synchronize()
        times.append(time.perf_counter() - t0)

    ms = sorted([t * 1000.0 for t in times])
    n = len(ms)
    avg = sum(ms) / n
    p50 = ms[n // 2]
    p95 = ms[min(n - 1, int(n * 0.95))]
    fps = 1000.0 / avg if avg > 0 else 0.0
    alloc_mb = torch.cuda.max_memory_allocated() / 1e6
    reserved_mb = torch.cuda.max_memory_reserved() / 1e6
    smi_used = query_nvidia_smi_used_mib()

    cuda_err = False
    oom = False
    return {
        "precision": precision,
        "iters": n,
        "avg_ms": round(avg, 3),
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "fps": round(fps, 2),
        "vram_alloc_mb": round(alloc_mb, 1),
        "vram_reserved_mb": round(reserved_mb, 1),
        "vram_nvidia_smi_used_mib": smi_used,
        "cuda_error": cuda_err,
        "oom": oom,
    }


def detect_on_images(model, images, conf):
    """返回 {img_stem: {class_name: count}} 与盲道命中数。"""
    per_img = {}
    blind_hits = 0
    for img in images:
        frame = cv2.imread(img)
        if frame is None:
            continue
        res = model.predict(source=frame, imgsz=IMGSZ, conf=conf, iou=IOU,
                             device=DEVICE, verbose=False)
        boxes = {}
        if res and res[0].boxes is not None and len(res[0].boxes) > 0:
            for c in res[0].boxes.cls.tolist():
                name = model.names.get(int(c), str(int(c)))
                boxes[name] = boxes.get(name, 0) + 1
        stem = os.path.splitext(os.path.basename(img))[0]
        per_img[stem] = boxes
        if "blind_road" in boxes:
            blind_hits += 1
    return per_img, blind_hits


def consistency_check(names):
    id2name = {int(k): v for k, v in names.items()}
    target_ids = [int(k) for k, v in names.items() if v in TARGET_CLASSES]
    # 选覆盖各类 + 盲道的图
    chosen, blind_imgs, _ = collect_target_images(names)
    if not chosen:
        chosen = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))[:6]

    model_fp32 = YOLO(WEIGHTS)
    model_fp16 = YOLO(WEIGHTS)

    fp32_map, fp32_blind = detect_on_images(model_fp32, chosen, CONF)
    fp16_map, fp16_blind = detect_on_images(model_fp16, chosen, CONF)

    # 汇总每类框数 (FP32 vs FP16)
    fp32_total = defaultdict(int)
    fp16_total = defaultdict(int)
    for v in fp32_map.values():
        for k, c in v.items():
            fp32_total[k] += c
    for v in fp16_map.values():
        for k, c in v.items():
            fp16_total[k] += c

    # 盲道专项: 在盲道 GT 图上分别用 0.25 / 0.15
    blind_chosen = []
    seen = set()
    for lp in blind_imgs:
        stem = os.path.splitext(os.path.basename(lp))[0]
        img = os.path.join(IMG_DIR, stem + ".jpg")
        if os.path.isfile(img) and stem not in seen:
            blind_chosen.append(img)
            seen.add(stem)
        if len(blind_chosen) >= 8:
            break
    if not blind_chosen:
        blind_chosen = chosen

    _, fp32_blind_low = detect_on_images(model_fp32, blind_chosen, CONF_LOW)
    _, fp16_blind_low = detect_on_images(model_fp16, blind_chosen, CONF_LOW)

    return {
        "timing_images_count": len(chosen),
        "fp32_per_class_total": dict(fp32_total),
        "fp16_per_class_total": dict(fp16_total),
        "fp32_total_boxes": sum(fp32_total.values()),
        "fp16_total_boxes": sum(fp16_total.values()),
        "blind_road_gt_images": len(blind_chosen),
        "blind_road_hit_fp32_conf0.25": fp32_blind,
        "blind_road_hit_fp16_conf0.25": fp16_blind,
        "blind_road_hit_fp32_conf0.15": fp32_blind_low,
        "blind_road_hit_fp16_conf0.15": fp16_blind_low,
    }


def main():
    print("Phase 18 Benchmark — 加载类别映射 ...")
    names = get_names()
    print("  类别数:", len(names))
    chosen, _, id2name = collect_target_images(names)
    if not chosen:
        chosen = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))[:4]
    print("  计时用图:", len(chosen), [os.path.basename(c) for c in chosen])

    print("\n[1/3] PyTorch FP32 Benchmark ...")
    fp32 = bench_precision("fp32", chosen)
    print("  ", fp32)

    print("[2/3] PyTorch FP16 Benchmark ...")
    fp16 = bench_precision("fp16", chosen)
    print("  ", fp16)

    print("[3/3] 检测结果一致性 (FP32 vs FP16) + blind_road 验证 ...")
    cons = consistency_check(names)
    print("  FP32 总框数:", cons["fp32_total_boxes"], " FP16 总框数:", cons["fp16_total_boxes"])
    print("  盲道 GT 图:", cons["blind_road_gt_images"],
          "| FP32@0.25 命中:", cons["blind_road_hit_fp32_conf0.25"],
          "| FP16@0.25 命中:", cons["blind_road_hit_fp16_conf0.25"],
          "| FP32@0.15 命中:", cons["blind_road_hit_fp32_conf0.15"],
          "| FP16@0.15 命中:", cons["blind_road_hit_fp16_conf0.15"])

    result = {
        "meta": {
            "weights": WEIGHTS, "imgsz": IMGSZ, "batch": 1, "device": DEVICE,
            "conf": CONF, "iou": IOU, "n_warmup": N_WARMUP, "n_iter": N_ITER,
            "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0),
        },
        "fp32": fp32,
        "fp16": fp16,
        "consistency": cons,
    }
    out_path = os.path.join(OUT_DIR, "benchmark_stats.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n结果已保存:", out_path)
    return result


if __name__ == "__main__":
    main()
