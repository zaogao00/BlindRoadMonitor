# -*- coding: utf-8 -*-
"""Phase 12 — 数据可视化质量检查 (visual QA)

- 从 datasets/processed/images/train 随机采样 >= 100 张 (优先覆盖含 blind_road 的图)
- 把图片与 YOLO 标签 (检测框 + 类名) 绘制到一起
- 数值校验: 坐标范围 / 尺寸 / 类 ID / 空标签 / 非法行
- 输出: datasets/preview/ (每张预览图 + 汇总拼贴)
- 检查结果写入 docs/dataset_quality_report.md 所需 JSON: docs/dataset_quality_stats.json
"""
import json
import os
import random
import sys
from collections import Counter

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

PROC = r"D:\BlindRoadMonitor\datasets\processed"
PREVIEW = r"D:\BlindRoadMonitor\datasets\preview"
STATS_JSON = r"D:\BlindRoadMonitor\docs\dataset_quality_stats.json"
SEED = 20260902
N_SAMPLE = 120          # >= 100 张
MAX_BLIND = 30          # 含 blind_road 的图最多取这么多 (确保核心类被检查)

NAMES = [
    "blind_road", "person", "pole", "car", "tree", "motorcycle",
    "warning_column", "crosswalk", "bicycle", "green_light", "red_light",
    "roadblock", "cone", "truck", "sign", "trash_bin", "bus", "tricycle",
    "fire_hydrant", "dog", "stairs", "manhole", "guard_rail", "chair",
    "bench", "plant_pot",
]

# 每类固定颜色 (BGR)
COLORS = [
    (0, 255, 0),    # blind_road 绿
    (255, 0, 0),    # person
    (255, 200, 0),  # pole
    (255, 0, 255),  # car
    (0, 255, 255),  # tree
    (128, 0, 255),
    (0, 128, 255),
    (255, 255, 0),
    (0, 165, 255),
    (128, 255, 0),
    (0, 255, 128),
    (200, 0, 0),
    (255, 128, 0),
    (0, 0, 255),
    (255, 255, 255),
    (170, 0, 255),
    (0, 170, 255),
    (255, 0, 128),
    (128, 128, 255),
    (255, 128, 128),
    (0, 128, 128),
    (128, 255, 128),
    (255, 170, 0),
    (170, 255, 170),
    (255, 170, 170),
    (170, 170, 255),
]


def pick_samples():
    """返回 (stem, img_path, lbl_path) 列表: 优先含 blind_road, 其余随机。"""
    img_dir = os.path.join(PROC, "images", "train")
    lbl_dir = os.path.join(PROC, "labels", "train")
    all_stems = sorted(
        s[:-4] for s in os.listdir(img_dir) if s.lower().endswith(".jpg")
    )
    # 找出含 blind_road 的标签
    blind_stems = []
    others = []
    for stem in all_stems:
        lp = os.path.join(lbl_dir, stem + ".txt")
        try:
            with open(lp, encoding="utf-8") as f:
                first = f.read(200)
            if first.split()[0] == "0" if first.split() else False:
                blind_stems.append(stem)
                continue
        except Exception:
            pass
        others.append(stem)

    rng = random.Random(SEED)
    rng.shuffle(others)
    blind_sample = blind_stems[:MAX_BLIND]
    rest = others[: max(0, N_SAMPLE - len(blind_sample))]
    chosen = blind_sample + rest
    rng.shuffle(chosen)  # 打乱顺序便于浏览
    out = []
    for stem in chosen:
        out.append(
            (stem, os.path.join(img_dir, stem + ".jpg"), os.path.join(lbl_dir, stem + ".txt"))
        )
    return out, len(blind_stems), len(all_stems)


def draw(img, boxes):
    """boxes: [(cid, cx, cy, w, h, raw)]; 返回绘制后的图 (缩放到宽<=720)。"""
    h, w = img.shape[:2]
    scale = 1.0
    if w > 720:
        scale = 720.0 / w
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    hh, ww = img.shape[:2]
    for cid, cx, cy, bw, bh, raw in boxes:
        x1 = int((cx - bw / 2) * ww)
        y1 = int((cy - bh / 2) * hh)
        x2 = int((cx + bw / 2) * ww)
        y2 = int((cy + bh / 2) * hh)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(ww - 1, x2), min(hh - 1, y2)
        color = COLORS[cid % len(COLORS)]
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f"{cid}:{NAMES[cid]}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        ty = y1 - 4 if y1 - th - 4 > 0 else y1 + th + 4
        cv2.rectangle(img, (x1, ty - th - 4), (x1 + tw + 4, ty + 2), color, -1)
        cv2.putText(img, label, (x1 + 2, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    return img


def parse_label(lp):
    """返回 (boxes, issues)。issues: list[str] 记录数值问题。"""
    boxes = []
    issues = []
    with open(lp, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            parts = line.split()
            if not parts:
                continue
            if len(parts) != 5:
                issues.append(f"line{ln}: 非5列 ({len(parts)})")
                continue
            try:
                cid = int(parts[0])
                cx, cy, bw, bh = (float(x) for x in parts[1:])
            except ValueError:
                issues.append(f"line{ln}: 数值解析失败")
                continue
            if not (0 <= cid < len(NAMES)):
                issues.append(f"line{ln}: 类ID越界 {cid}")
                continue
            if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
                issues.append(f"line{ln}: 中心越界 ({cx:.4f},{cy:.4f})")
            if not (0.0 < bw <= 1.0 and 0.0 < bh <= 1.0):
                issues.append(f"line{ln}: 宽高非法 ({bw:.4f},{bh:.4f})")
            boxes.append((cid, cx, cy, bw, bh, line.strip()))
    return boxes, issues


def main():
    os.makedirs(PREVIEW, exist_ok=True)
    samples, n_blind_total, n_all = pick_samples()
    print(f"[1] 采样: {len(samples)} 张 (train 共 {n_all}, 含 blind_road {n_blind_total})")

    per_file = []
    class_hit = Counter()
    total_boxes = 0
    empty_count = 0
    issues_all = []

    for idx, (stem, ip, lp) in enumerate(samples, 1):
        img = cv2.imread(ip)
        if img is None:
            per_file.append({"stem": stem, "status": "无法使用", "reason": "图片读取失败"})
            continue
        boxes, issues = parse_label(lp)
        if not boxes:
            empty_count += 1
        for cid, *_ in boxes:
            class_hit[NAMES[cid]] += 1
        total_boxes += len(boxes)
        if issues:
            issues_all.append({"stem": stem, "issues": issues})
        drawn = draw(img, boxes)
        out_name = f"{idx:03d}_{stem}.jpg"
        cv2.imwrite(os.path.join(PREVIEW, out_name), drawn, [cv2.IMWRITE_JPEG_QUALITY, 90])
        per_file.append(
            {
                "stem": stem,
                "file": out_name,
                "boxes": len(boxes),
                "classes": [NAMES[cid] for cid, *_ in boxes],
                "has_blind_road": 0 in [b[0] for b in boxes],
                "empty": not boxes,
            }
        )

    # 汇总拼贴 (12 宫格)
    files = sorted(f for f in os.listdir(PREVIEW) if f.lower().endswith(".jpg"))
    thumbs = []
    for f in files:
        im = cv2.imread(os.path.join(PREVIEW, f))
        if im is None:
            continue
        thumbs.append(cv2.resize(im, (360, 240)))
    n_grid = len(thumbs)
    ncols = 4
    nrows = (n_grid + ncols - 1) // ncols
    canvas = np.full((nrows * 240 + (nrows + 1) * 10, ncols * 360 + (ncols + 1) * 10, 3), 30, np.uint8)
    for i, t in enumerate(thumbs):
        r, c = divmod(i, ncols)
        y0 = r * 240 + (r + 1) * 10
        x0 = c * 360 + (c + 1) * 10
        canvas[y0 : y0 + 240, x0 : x0 + 360] = t
    cv2.imwrite(os.path.join(PREVIEW, "_summary_grid.jpg"), canvas, [cv2.IMWRITE_JPEG_QUALITY, 85])

    stats = {
        "seed": SEED,
        "n_sampled": len(samples),
        "n_train_total": n_all,
        "n_blind_total_in_train": n_blind_total,
        "n_drawn": len(per_file),
        "total_boxes": total_boxes,
        "empty_labels": empty_count,
        "class_hit": dict(class_hit.most_common()),
        "numeric_issue_files": issues_all,
        "status": "NORMAL" if not issues_all else "ISSUES_FOUND",
    }
    with open(STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"[2] 绘制完成: {len(per_file)} 张 -> {PREVIEW}")
    print(f"    实例总数: {total_boxes} | 空标签: {empty_count} | 数值问题文件: {len(issues_all)}")
    print(f"    盲道命中: {class_hit.get('blind_road', 0)} 实例")
    print(f"[3] 统计: {STATS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
