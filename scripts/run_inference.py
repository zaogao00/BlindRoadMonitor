# -*- coding: utf-8 -*-
"""Phase 16 — Inference Validation

验证 Phase 15 的 best.pt 在真实推理阶段是否可靠。
- 指标复现: 用 best.pt 在 test 划分复现 Phase 15 指标 (mAP50/mAP50-95/P/R/每类)
- 定性可视化: runs/yolov8n_prod_b32/inference/ 下分 A~G 七类 + GT vs Pred 对照
- 失败模式: 统计 blind_road 漏检/误检、长尾类、易混淆类
- 性能基准: RTX 5070 上 avg 推理时间 / FPS / 显存 / 模型大小 (可选 CPU 小样本)
- 输出: docs/inference_stats.json (供 docs/inference_report.md 使用)

安全约束: 不修改模型/数据/Phase15 结果; 不导出部署模型; 不覆盖旧实验; 产物写到 inference/ 子目录。
沙箱适配 (同 Phase 13/14/15): YOLO_CONFIG_DIR / MPLCONFIGDIR / monkeypatch ThreadPool / workers=0。
仅用 PIL (本机未装 OpenCV)。
"""
import os
import sys
import json
import time
import random
import argparse
from pathlib import Path

ROOT = r"D:\BlindRoadMonitor"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:
    from disk_manager import get_disk_info  # 可选, 推理只读, 失败也不阻断
except Exception:
    get_disk_info = None

# ---- 沙箱适配 (同 Phase 13/14/15) ----
os.environ["YOLO_CONFIG_DIR"] = r"D:\BlindRoadMonitor\.yolo_config"
os.environ["MPLCONFIGDIR"] = r"D:\BlindRoadMonitor\.yolo_config\mpl"
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import torch
import ultralytics.data.dataset as _uds
from concurrent.futures import ThreadPoolExecutor


class _NoPipeThreadPool:
    """纯线程池替换 ultralytics 的 ThreadPool (命名管道被沙箱拒)。仅影响缓存扫描。"""
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

from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO

# ---- 路径 ----
BEST_PT = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "weights", "best.pt")
DATA = os.path.join(ROOT, "datasets", "processed", "data.yaml")
PHASE15_JSON = os.path.join(ROOT, "docs", "final_training_stats.json")
OUT_JSON = os.path.join(ROOT, "docs", "inference_stats.json")

FOCUS_CLASSES = ["blind_road", "truck", "guard_rail", "plant_pot",
                 "green_light", "red_light", "manhole", "crosswalk"]
LONGTAIL = ["truck", "guard_rail", "plant_pot"]
CONFUSABLE = ["green_light", "red_light", "manhole"]


def iou(ba, bb):
    xa, ya = max(ba[0], bb[0]), max(ba[1], bb[1])
    xb, yb = min(ba[2], bb[2]), min(ba[3], bb[3])
    w, h = max(0.0, xb - xa), max(0.0, yb - ya)
    inter = w * h
    aa = max(0.0, (ba[2] - ba[0]) * (ba[3] - ba[1]))
    ab = max(0.0, (bb[2] - bb[0]) * (bb[3] - bb[1]))
    union = aa + ab - inter
    return inter / union if union > 0 else 0.0


def load_gt(label_path, w, h):
    """读取 YOLO 标签, 返回 [(xyxy, cls), ...] (像素坐标)。"""
    out = []
    if not label_path or not os.path.isfile(label_path):
        return out
    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                c = int(float(parts[0]))
                cx, cy, nw, nh = (float(parts[1]), float(parts[2]),
                                  float(parts[3]), float(parts[4]))
            except ValueError:
                continue
            x1 = (cx - nw / 2) * w
            x2 = (cx + nw / 2) * w
            y1 = (cy - nh / 2) * h
            y2 = (cy + nh / 2) * h
            out.append(([x1, y1, x2, y2], c))
    return out


def draw_boxes(img, boxes, color, names, font, prefix=""):
    d = ImageDraw.Draw(img)
    for (x1, y1, x2, y2, c, conf) in boxes:
        d.rectangle([x1, y1, x2, y2], outline=color, width=2)
        txt = f"{prefix}{names[c]}" + (f" {conf:.2f}" if conf is not None else "")
        d.text((x1, max(0, y1 - 11)), txt, fill=color, font=font)
    return img


def get_font():
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=BEST_PT)
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--split", default="test")
    ap.add_argument("--output", default=os.path.join(ROOT, "runs", "yolov8n_prod_b32", "inference"))
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.45)
    ap.add_argument("--max-vis", type=int, default=12)
    ap.add_argument("--bench-n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260902)
    ap.add_argument("--cpu", action="store_true", help="强制全部用 CPU (含指标复现)")
    ap.add_argument("--no-cpu-bench", action="store_true", help="跳过额外 CPU 小样本基准")
    args = ap.parse_args()

    random.seed(args.seed)
    device = "cpu" if args.cpu else "0"
    font = get_font()
    os.makedirs(args.output, exist_ok=True)
    for sub in ["A_random", "B_good", "C_lowconf", "D_missed", "E_falsepos",
                "F_longtail", "G_confusable", "gt_vs_pred"]:
        os.makedirs(os.path.join(args.output, sub), exist_ok=True)

    model = YOLO(args.weights)
    names = model.names  # {idx: name}
    n_cls = model.model.nc

    # ---- 1) 指标复现 (test 划分) ----
    print(f"[1] 指标复现: val(data={args.data}, split={args.split}, device={device}) ...")
    t0 = time.time()
    res = model.val(data=args.data, imgsz=args.imgsz, batch=32, device=device,
                    split=args.split, plots=False, verbose=False, workers=0)
    repro = dict(
        images=int(res.box.niou if hasattr(res.box, "niou") else 0),
        mAP50=round(float(res.box.map50), 4),
        mAP50_95=round(float(res.box.map), 4),
        precision=round(float(res.box.mp), 4),
        recall=round(float(res.box.mr), 4),
    )
    repro_pc = {}
    for i in range(n_cls):
        name = names[i]
        try:
            repro_pc[name] = dict(
                P=round(float(res.box.p[i]), 4),
                R=round(float(res.box.r[i]), 4),
                mAP50=round(float(res.box.ap50[i]), 4),
                mAP50_95=round(float(res.box.ap[i]), 4),
            )
        except IndexError:
            repro_pc[name] = dict(P=0.0, R=0.0, mAP50=0.0, mAP50_95=0.0,
                                  note="该划分无此类目标")
    print(f"[1] 复现完成 {time.time()-t0:.1f}s: mAP50={repro['mAP50']} "
          f"mAP50-95={repro['mAP50_95']} P={repro['precision']} R={repro['recall']}")

    # ---- Phase 15 指标 (用于对比) ----
    phase15 = {}
    try:
        with open(PHASE15_JSON, "r", encoding="utf-8") as f:
            phase15 = json.load(f)
    except Exception as e:
        print(f"[warn] 读取 Phase15 统计失败: {e}")
    p15_test = phase15.get("test", {}).get("overall", {})
    p15_test_pc = phase15.get("test", {}).get("per_class", {})

    def diff(a, b):
        if a is None or b is None:
            return None
        return round(float(a) - float(b), 4)

    diff_overall = {k: diff(repro.get(k), p15_test.get(k)) for k in
                    ["mAP50", "mAP50_95", "precision", "recall"]}

    # ---- 2) 逐图预测 + GT 匹配 (采样/失败分析) ----
    img_dir = os.path.join(ROOT, "datasets", "processed", "images", args.split)
    lbl_dir = os.path.join(ROOT, "datasets", "processed", "labels", args.split)
    files = sorted([os.path.join(img_dir, f) for f in os.listdir(img_dir)
                    if f.lower().endswith((".jpg", ".png"))])
    print(f"[2] 逐图预测: {len(files)} 张 ({args.split}) device={device} ...")
    cls_index = {n: i for i, n in names.items()}

    # 每图记录: gt_boxes, pred_boxes, fn(漏检)/fp(误检) 计数
    records = []
    per_class_fn = {n: 0 for n in names.values()}
    per_class_fp = {n: 0 for n in names.values()}
    blind_fn_images, blind_fp_images = [], []
    any_fn_images, any_fp_images = [], []
    lowconf_images, good_images = [], []
    longtail_images, confusable_images = [], []

    # 分块预测: 列表源会被 Ultralytics 整体载入(忽略 batch)导致 OOM,
    # 故每次仅把 CHUNK 张图送入 GPU 并逐张匹配, 跑完即释放。
    t0 = time.time()
    CHUNK = 128
    n_done = 0
    for ci in range(0, len(files), CHUNK):
        chunk = files[ci:ci + CHUNK]
        chunk_preds = model.predict(source=chunk, imgsz=args.imgsz, conf=args.conf,
                                     iou=args.iou, device=device, batch=32,
                                     workers=0, verbose=False, stream=False)
        for path, r in zip(chunk, chunk_preds):
            w, h = r.orig_shape[1], r.orig_shape[0]
            lbl = os.path.join(lbl_dir, os.path.splitext(os.path.basename(path))[0] + ".txt")
            gt = load_gt(lbl, w, h)
            pb = []
            if r.boxes is not None and len(r.boxes) > 0:
                for b, c, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(),
                                    r.boxes.conf.tolist()):
                    pb.append((b[0], b[1], b[2], b[3], int(c), float(cf)))

            # 匹配: fn = GT 无匹配预测; fp = 预测无匹配 GT (同类的 iou>=0.5)
            fn_set, fp_set = set(), set()
            for gi, (gb, gc) in enumerate(gt):
                gname = names[gc]
                matched = False
            for (bx1, by1, bx2, by2, pc_, cf_) in pb:
                if pc_ == gc and iou(gb, (bx1, by1, bx2, by2)) >= 0.5 and cf_ >= args.conf:
                    matched = True
                    break
                if not matched:
                    fn_set.add(gname)
                    per_class_fn[gname] += 1
            for (bx1, by1, bx2, by2, pc_, cf_) in pb:
                pname = names[pc_]
                ok = False
                for gi, (gb, gc) in enumerate(gt):
                    if gc == pc_ and iou(gb, (bx1, by1, bx2, by2)) >= 0.5:
                        ok = True
                        break
                if not ok:
                    fp_set.add(pname)
                    per_class_fp[pname] += 1

            rec = dict(path=path, gt=gt, pred=pb, fn=fn_set, fp=fp_set,
                       max_conf=max([cf for *_, cf in pb], default=0.0))
            records.append(rec)
            gt_names = {names[c] for _, c in gt}
            pred_names = {names[c] for *_, c, _ in pb}

            if "blind_road" in fn_set:
                blind_fn_images.append(rec)
            if "blind_road" in fp_set:
                blind_fp_images.append(rec)
            if fn_set:
                any_fn_images.append(rec)
            if fp_set:
                any_fp_images.append(rec)
            if rec["max_conf"] >= 0.7 and (gt and not fn_set):
                good_images.append(rec)
            if any(cf < 0.45 for *_, cf in pb):
                lowconf_images.append(rec)
            if gt_names & set(LONGTAIL):
                longtail_images.append(rec)
            if (gt_names | pred_names) & set(CONFUSABLE):
                confusable_images.append(rec)
        n_done += len(chunk)
        if (ci // CHUNK) % 4 == 0:
            print(f"[2] 进度 {n_done}/{len(files)}")
    print(f"[2] 预测+匹配完成 {time.time()-t0:.1f}s")

    print(f"[2] 失败统计: blind_road 漏检图={len(blind_fn_images)} "
          f"误检图={len(blind_fp_images)} | 任意漏检图={len(any_fn_images)} "
          f"任意误检图={len(any_fp_images)}")

    # ---- 3) 样本挑选 + 可视化 ----
    def sample(lst, k):
        if len(lst) <= k:
            return lst
        return random.sample(lst, k)

    def save_pred(rec, sub, kind):
        img = Image.open(rec["path"]).convert("RGB")
        W, H = img.size
        boxes = [(x1, y1, x2, y2, c, cf) for (x1, y1, x2, y2, c, cf) in rec["pred"]]
        draw_boxes(img, boxes, (255, 140, 0), names, font, "P:")
        out = os.path.join(args.output, sub,
                            f"{kind}_{os.path.splitext(os.path.basename(rec['path']))[0]}.png")
        img.save(out)

    def save_gtvspred(rec, kind):
        base = Image.open(rec["path"]).convert("RGB")
        W, H = base.size
        gt_img = base.copy()
        draw_boxes(gt_img, [(b[0], b[1], b[2], b[3], c, None) for (b, c) in rec["gt"]],
                   (0, 200, 255), names, font, "GT:")
        pred_img = base.copy()
        draw_boxes(pred_img, [(x1, y1, x2, y2, c, cf) for (x1, y1, x2, y2, c, cf) in rec["pred"]],
                   (255, 140, 0), names, font, "P:")
        gap = 8
        canvas = Image.new("RGB", (W * 2 + gap, H), (255, 255, 255))
        canvas.paste(gt_img, (0, 0))
        canvas.paste(pred_img, (W + gap, 0))
        ImageDraw.Draw(canvas).text((6, 4), "LEFT=GT", fill=(0, 120, 200), font=font)
        ImageDraw.Draw(canvas).text((W + gap + 6, 4), "RIGHT=PRED", fill=(200, 100, 0), font=font)
        out = os.path.join(args.output, "gt_vs_pred",
                            f"{kind}_{os.path.splitext(os.path.basename(rec['path']))[0]}.png")
        canvas.save(out)

    # A 随机
    for rec in sample(records, args.max_vis):
        save_pred(rec, "A_random", "rand")
    # B 好样本 (高置信且无漏检)
    for rec in sample(good_images, args.max_vis):
        save_gtvspred(rec, "good")
    # C 低置信
    for rec in sample(lowconf_images, args.max_vis):
        save_gtvspred(rec, "lowconf")
    # D 漏检 (重点 blind_road)
    for rec in sample(blind_fn_images or any_fn_images, args.max_vis):
        save_gtvspred(rec, "missed")
    # E 误检
    for rec in sample(blind_fp_images or any_fp_images, args.max_vis):
        save_gtvspred(rec, "falsepos")
    # F 长尾
    for rec in sample(longtail_images, args.max_vis):
        save_gtvspred(rec, "longtail")
    # G 易混淆
    for rec in sample(confusable_images, args.max_vis):
        save_gtvspred(rec, "confus")

    print(f"[3] 可视化已写入 {args.output}")

    # ---- 4) 性能基准 ----
    print(f"[4] 性能基准 device={device} ...")
    perf = dict(device=device)
    # 模型大小
    try:
        perf["model_size_mb"] = round(os.path.getsize(args.weights) / 1e6, 2)
    except Exception:
        perf["model_size_mb"] = None

    bench_files = files[: min(args.bench_n, len(files))]
    # warmup
    _ = model.predict(source=bench_files[: min(8, len(bench_files))], imgsz=args.imgsz,
                      conf=args.conf, device=device, batch=32, verbose=False)
    # 单图端到端
    if device != "cpu":
        torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    for f in bench_files:
        model.predict(source=f, imgsz=args.imgsz, conf=args.conf, device=device,
                      verbose=False)
    t1 = time.time()
    perf["single_ms_per_img"] = round((t1 - t0) / len(bench_files) * 1000, 2)
    perf["single_fps"] = round(len(bench_files) / (t1 - t0), 2)
    # 批量吞吐 (含 batch 开销)
    t0 = time.time()
    model.predict(source=bench_files, imgsz=args.imgsz, conf=args.conf, device=device,
                  batch=32, verbose=False)
    t1 = time.time()
    perf["batched_ms_per_img"] = round((t1 - t0) / len(bench_files) * 1000, 2)
    perf["batched_fps"] = round(len(bench_files) / (t1 - t0), 2)
    if device != "cpu":
        perf["gpu_vram_mb_peak"] = round(torch.cuda.max_memory_allocated() / 1024 ** 2, 1)
    else:
        perf["gpu_vram_mb_peak"] = None

    # 额外 CPU 小样本 (不长时间)
    if device != "cpu" and not args.no_cpu_bench:
        cpu_n = min(20, len(files))
        cf = files[:cpu_n]
        _ = model.predict(source=cf[: min(4, len(cf))], imgsz=args.imgsz, conf=args.conf,
                          device="cpu", verbose=False)
        t0 = time.time()
        for f in cf:
            model.predict(source=f, imgsz=args.imgsz, conf=args.conf, device="cpu", verbose=False)
        t1 = time.time()
        perf["cpu_single_ms_per_img"] = round((t1 - t0) / len(cf) * 1000, 2)
        perf["cpu_single_fps"] = round(len(cf) / (t1 - t0), 2)
    print(f"[4] 完成: single={perf.get('single_fps')} FPS "
          f"batched={perf.get('batched_fps')} FPS "
          f"vram={perf.get('gpu_vram_mb_peak')}MB")

    # ---- 5) 汇总 JSON ----
    stats = dict(
        phase="Phase 16 Inference Validation",
        model_path=str(args.weights),
        model_size_mb=perf.get("model_size_mb"),
        data=str(args.data),
        split=args.split,
        imgsz=args.imgsz,
        conf_threshold=args.conf,
        test_reproduced=repro,
        test_per_class=repro_pc,
        phase15_test=p15_test,
        phase15_test_per_class=p15_test_pc,
        diff_vs_phase15=dict(overall=diff_overall),
        failure_counts=dict(
            blind_road_missed_images=len(blind_fn_images),
            blind_road_falsepos_images=len(blind_fp_images),
            any_missed_images=len(any_fn_images),
            any_falsepos_images=len(any_fp_images),
            per_class_missed=per_class_fn,
            per_class_falsepos=per_class_fp,
        ),
        sample_counts=dict(
            A_random=min(args.max_vis, len(records)),
            B_good=len(good_images),
            C_lowconf=len(lowconf_images),
            D_missed=len(blind_fn_images or any_fn_images),
            E_falsepos=len(blind_fp_images or any_fp_images),
            F_longtail=len(longtail_images),
            G_confusable=len(confusable_images),
        ),
        performance=perf,
    )
    if get_disk_info is not None:
        try:
            di = get_disk_info("D:\\")
            stats["disk_end"] = dict(free_gb=round(di.free_gb, 1), status=di.status)
        except Exception:
            pass
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"[done] 统计 -> {OUT_JSON}")
    print("=" * 60)
    print(f"test 复现 mAP50={repro['mAP50']} (Phase15={p15_test.get('mAP50')}) "
          f"diff={diff_overall.get('mAP50')}")
    print(f"blind_road 复现 mAP50={repro_pc.get('blind_road', {}).get('mAP50')} "
          f"(Phase15={p15_test_pc.get('blind_road', {}).get('mAP50')})")
    print(f"blind_road 漏检图={len(blind_fn_images)} 误检图={len(blind_fp_images)}")


if __name__ == "__main__":
    main()
