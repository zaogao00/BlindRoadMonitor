# -*- coding: utf-8 -*-
"""Phase 20 — 集成验证脚本 (真实模型 + 真实图片, 非单元测试)。

用途:
  1) images 模式: 在 test 集上跑 best.pt, 统计盲道/障碍物/疑似占用的分布与 FPS,
     并抽样保存标注图 (供人工核对"为什么判定为疑似占用")。
  2) loop   模式: 用图片循环模拟视频流, 连续跑 N 秒, 观察 FPS / 线程数 / 内存 / 显存
     是否稳定 (规格 §二十九 连续运行测试)。

额外分析 (本阶段的关键度量):
  - occupancy 一致性: 同一张图分别用 **GT 框** 和 **预测框** 跑 SpatialChecker,
    对比占用判定结果。用来把"检测误差"与"几何规则误差"分开。

约束: 不训练 / 不改 best.pt / 不改数据集 / 只读 labels。
用法:
  python scripts/run_phase20_test.py --mode images --limit 200
  python scripts/run_phase20_test.py --mode loop   --duration 300
"""
import os
import sys
import time
import argparse
import threading

ROOT = r"D:\BlindRoadMonitor"
sys.path.insert(0, os.path.join(ROOT, "backend"))

MODEL = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "weights", "best.pt")
IMG_DIR = os.path.join(ROOT, "datasets", "processed", "images", "test")
LBL_DIR = os.path.join(ROOT, "datasets", "processed", "labels", "test")
OUT_DIR = os.path.join(ROOT, "outputs", "phase20_vis")

# 与 AlertManager 保持一致的"非障碍物"类别 (盲道/斑马线/红绿灯)
from alert import AlertManager, OBSTACLE_CLASS_INDICES  # noqa: E402
from spatial import classify  # noqa: E402


def _yolo_txt_to_boxes(txt_path, w, h):
    """读 YOLO txt -> [(x1,y1,x2,y2,cls,conf)] (GT 置信度记 1.0)。"""
    out = []
    if not os.path.isfile(txt_path):
        return out
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            p = line.strip().split()
            if len(p) < 5:
                continue
            try:
                c = int(float(p[0]))
                cx, cy, bw, bh = (float(v) for v in p[1:5])
            except ValueError:
                continue
            x1 = (cx - bw / 2.0) * w
            y1 = (cy - bh / 2.0) * h
            x2 = (cx + bw / 2.0) * w
            y2 = (cy + bh / 2.0) * h
            out.append((x1, y1, x2, y2, c, 1.0))
    return out


def _split_boxes(boxes, names):
    """按 AlertManager 的同一套类别定义拆分盲道/障碍物 (不复制第二份类别列表)。"""
    blind, obs = [], []
    for (x1, y1, x2, y2, c, cf) in boxes:
        nm = names.get(c, str(c))
        if nm == "blind_road":
            blind.append((x1, y1, x2, y2))
        elif c in OBSTACLE_CLASS_INDICES:
            obs.append({"box": (x1, y1, x2, y2), "cls": c, "class": nm,
                        "confidence": cf, "zh": nm})
    return blind, obs


def _gpu_mb():
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / 1024.0 / 1024.0
    except Exception:
        pass
    return None


def _rss_mb():
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1024.0 / 1024.0
    except Exception:
        return None


def _list_files(sample, limit):
    """选择测试图片。

    注意: 本数据集 blind_road 标注很稀疏 (test 4163 张中仅 296 张含 class 0, 约 7%),
    这是 Phase 11 数据转换的既有特性。因此不能按文件名顺序抽样 (前段几乎全是 ROD 图,
    无盲道), 必须按标签分组:
      blind : 只取 GT 含 blind_road 的图 -> 用于**漏报**分析 (应能判出占用)
      ctrl  : 只取 GT 不含 blind_road 的图 -> 用于**误报**分析 (不应轻易判占用)
      seq   : 原始顺序 (仅作对照)
    """
    allf = sorted([f for f in os.listdir(IMG_DIR)
                   if f.lower().endswith((".jpg", ".jpeg", ".png"))])
    if sample == "seq":
        return allf[:limit]
    blind, ctrl = [], []
    for fn in allf:
        txt = os.path.join(LBL_DIR, os.path.splitext(fn)[0] + ".txt")
        has_br = False
        if os.path.isfile(txt):
            with open(txt, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("0 "):
                        has_br = True
                        break
        (blind if has_br else ctrl).append(fn)
    if sample == "blind":
        return blind[:limit]
    return ctrl[:limit]


def run_images(det, limit, save_n, conf, sample):
    import cv2
    files = _list_files(sample, limit)
    print(f"[images] sample={sample} 共 {len(files)} 张, model={MODEL}")

    alert = AlertManager(cooldown=2.5)
    stats = {
        "frames": 0, "with_blind": 0, "with_obs": 0, "both": 0,
        "lvl0": 0, "lvl1": 0, "lvl2": 0,
        "agree": 0, "disagree": 0, "gt_only_block": 0, "pred_only_block": 0,
    }
    t_infer = 0.0
    t_spatial = 0.0
    t_draw = 0.0
    saved = 0
    samples = []

    for i, fn in enumerate(files):
        path = os.path.join(IMG_DIR, fn)
        img = cv2.imread(path)
        if img is None:
            continue
        h, w = img.shape[:2]

        t0 = time.perf_counter()
        boxes, _ = det.infer(img)
        t_infer += time.perf_counter() - t0

        t0 = time.perf_counter()
        st = alert.update(boxes, det.names)
        t_spatial += time.perf_counter() - t0

        occ = st["occupancy"]
        stats["frames"] += 1
        if st["blind_road"]:
            stats["with_blind"] += 1
        if st["obstacle_count"] > 0:
            stats["with_obs"] += 1
        if st["blind_road"] and st["obstacle_count"] > 0:
            stats["both"] += 1
        stats["lvl%d" % st["alert_level"]] += 1

        # ---- GT vs 预测 的占用判定一致性 (分离检测误差与几何规则误差) ----
        gt = _yolo_txt_to_boxes(
            os.path.join(LBL_DIR, os.path.splitext(fn)[0] + ".txt"), w, h)
        gb, go = _split_boxes(gt, det.names)
        if gb and go:
            gt_occ = classify(gb, go)
            if bool(gt_occ["blocking"]) == bool(occ["blocking"]):
                stats["agree"] += 1
            else:
                stats["disagree"] += 1
                if gt_occ["blocking"] and not occ["blocking"]:
                    stats["gt_only_block"] += 1
                else:
                    stats["pred_only_block"] += 1

        # ---- 抽样保存 (优先 Level 2, 便于人工核对误报/漏报) ----
        if saved < save_n and occ["blocking"]:
            t0 = time.perf_counter()
            frame = det.draw(img, boxes, fps=None, occupancy=occ)
            t_draw += time.perf_counter() - t0
            os.makedirs(OUT_DIR, exist_ok=True)
            cv2.imwrite(os.path.join(OUT_DIR, f"p20_{saved:02d}_{fn}"), frame)
            saved += 1
            bo = occ["blocking_obstacles"][0]
            samples.append((fn, bo["class"], bo["iou"], bo["overlap_ratio"],
                            bo["center_inside"]))

        if (i + 1) % 50 == 0:
            print(f"  ... {i+1}/{len(files)}  L2={stats['lvl2']}  "
                  f"一致性={stats['agree']}/{stats['agree']+stats['disagree']}")

    alert.shutdown()
    n = max(1, stats["frames"])
    print("\n[images] 结果")
    print(f"  帧数                : {stats['frames']}")
    print(f"  检出盲道            : {stats['with_blind']} ({stats['with_blind']/n:.1%})")
    print(f"  检出障碍物          : {stats['with_obs']} ({stats['with_obs']/n:.1%})")
    print(f"  盲道+障碍物同时检出 : {stats['both']} ({stats['both']/n:.1%})")
    print(f"  Level 0 / 1 / 2     : {stats['lvl0']} / {stats['lvl1']} / {stats['lvl2']}"
          f"   (Level2 占比 {stats['lvl2']/n:.1%})")
    tot = stats["agree"] + stats["disagree"]
    if tot:
        print(f"  GT-预测 占用一致性   : {stats['agree']}/{tot} = {stats['agree']/tot:.1%}")
        print(f"    其中 GT判占用/预测未判 (漏报, 多为盲道或障碍物被漏检): "
              f"{stats['gt_only_block']}")
        print(f"    其中 预测判占用/GT未判 (误报, 多为检测框偏移或透视): "
              f"{stats['pred_only_block']}")
    print(f"  平均耗时 (ms/帧)    : infer={t_infer/n*1000:.1f}  "
          f"spatial+alert={t_spatial/n*1000:.3f}  draw={t_draw/max(1,saved)*1000:.1f}")
    print(f"  保存样本            : {saved} -> {OUT_DIR}")
    for s in samples[:10]:
        print(f"    {s[0]}: {s[1]} IoU={s[2]:.3f} 交叠={s[3]:.3f} 中心在内={s[4]}")
    return stats


def run_loop(det, duration, conf):
    import cv2
    # 用**含盲道 GT** 的图循环, 才能真实压测 SpatialChecker 判定路径 (否则一路 Level 1)
    files = _list_files("blind", 60)
    imgs = []
    for fn in files:
        im = cv2.imread(os.path.join(IMG_DIR, fn))
        if im is not None:
            imgs.append(im)
    if not imgs:
        print("[loop] 没有可用图片")
        return
    print(f"[loop] 连续运行 {duration}s, 循环 {len(imgs)} 张图模拟视频流")

    alert = AlertManager(cooldown=2.5)
    t_end = time.time() + duration
    frames = 0
    idx = 0
    last_report = time.time()
    t0 = time.time()
    thread_samples = []
    lvl_counts = {0: 0, 1: 0, 2: 0}
    errors = []

    try:
        while time.time() < t_end:
            img = imgs[idx % len(imgs)]
            idx += 1
            try:
                boxes, _ = det.infer(img)
                st = alert.update(boxes, det.names)
                if idx % 3 == 0:      # 抽样绘制, 覆盖绘制路径
                    det.draw(img, boxes, fps=None, occupancy=st["occupancy"])
                lvl_counts[st["alert_level"]] += 1
            except Exception as e:
                errors.append(f"{type(e).__name__}: {str(e)[:120]}")
                if len(errors) > 5:
                    break
            frames += 1
            if time.time() - last_report >= 30:
                el = time.time() - t0
                fps = frames / el if el else 0.0
                th = threading.active_count()
                thread_samples.append(th)
                print(f"  [{int(el)}s] FPS={fps:.1f}  帧={frames}  线程={th}  "
                      f"RSS={_rss_mb()}  显存={_gpu_mb()}  L0/1/2="
                      f"{lvl_counts[0]}/{lvl_counts[1]}/{lvl_counts[2]}")
                last_report = time.time()
    finally:
        alert.shutdown()

    el = time.time() - t0
    print("\n[loop] 结果")
    print(f"  总时长 / 帧数       : {el:.1f}s / {frames}  -> 平均 {frames/el:.1f} FPS")
    print(f"  L0 / L1 / L2        : {lvl_counts[0]} / {lvl_counts[1]} / {lvl_counts[2]}")
    print(f"  线程数样本          : {thread_samples} "
          f"(首={thread_samples[0] if thread_samples else '-'}, "
          f"末={thread_samples[-1] if thread_samples else '-'})")
    stable_th = (len(set(thread_samples)) <= 2) if thread_samples else True
    print(f"  线程数是否稳定      : {'PASS' if stable_th else 'FAIL'}")
    print(f"  RSS / 显存          : {_rss_mb()} MB / {_gpu_mb()} MB")
    print(f"  运行期异常          : {errors if errors else '无'} -> "
          f"{'PASS' if not errors else 'FAIL'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["images", "loop"], default="images")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--save-n", type=int, default=8)
    ap.add_argument("--duration", type=int, default=300)
    ap.add_argument("--conf", type=float, default=0.20)
    ap.add_argument("--sample", choices=["blind", "ctrl", "seq"], default="blind")
    args = ap.parse_args()

    if not os.path.isfile(MODEL):
        print(f"[FATAL] 模型不存在: {MODEL}")
        return 1

    from detector import Detector
    det = Detector(weights=MODEL, device="0", imgsz=640,
                   conf=args.conf, iou=0.45)
    print(f"[init] 模型已加载: nc={det.nc} conf={args.conf}")

    if args.mode == "images":
        groups = [args.sample]
        if args.sample == "blind":
            groups = ["blind", "ctrl"]   # 盲道组(漏报) + 对照组(误报) 一起跑
        for g in groups:
            print("\n" + "=" * 60)
            print(f"[group] {g}  "
                  f"({'漏报分析: GT 含盲道' if g == 'blind' else '误报分析: GT 不含盲道'})")
            print("=" * 60)
            run_images(det, args.limit, args.save_n, args.conf, g)
    else:
        run_loop(det, args.duration, args.conf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
