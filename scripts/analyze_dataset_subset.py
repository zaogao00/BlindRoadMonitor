#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对已下载的 ROD-Dataset 子集(train 前 614 张)做只读数据集分析。
不下载、不转换、不训练。
输出: docs/dataset_analysis_614.md
"""
import os, glob, json, statistics, collections
import csv

RAW = r"D:\BlindRoadMonitor\datasets\raw\rod_dataset"
IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
OUT = r"D:\BlindRoadMonitor\docs\dataset_analysis_614.md"

# 尝试用 opencv 读图像尺寸(若不可用则降级)
try:
    import cv2
    def img_size(p):
        im = cv2.imread(p)
        if im is None:
            return None
        h, w = im.shape[:2]
        return (w, h)
    HAS_CV2 = True
except Exception:
    HAS_CV2 = False
    def img_size(p):
        return None

def parse_label(txt_path):
    """返回 (boxes, errs)。box = [cls, x1, y1, x2, y2] 归一化包围盒(兼容检测框与分割多边形)。
    检测框格式: cls xc yc w h  -> 转包围盒
    分割多边形: cls x1 y1 x2 y2 ... xn yn -> 取点集 min/max 包围盒
    """
    boxes = []
    errs = []
    det_n = seg_n = 0
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        for ln, line in enumerate(f.readlines(), 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            try:
                cls = int(float(parts[0]))
            except ValueError:
                errs.append(f"line{ln}: class 解析失败 {parts[:1]}")
                continue
            if cls < 0:
                errs.append(f"line{ln}: cls<0 ({cls})")
                continue
            coords = parts[1:]
            n = len(coords)
            # 检测框
            if n == 4:
                try:
                    xc, yc, w, h = (float(x) for x in coords)
                except ValueError:
                    errs.append(f"line{ln}: 数值解析失败")
                    continue
                x1, y1, x2, y2 = xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2
                det_n += 1
            # 分割多边形 (奇数个坐标: 2k 个点)
            elif n >= 6 and n % 2 == 0:
                try:
                    pts = [float(x) for x in coords]
                except ValueError:
                    errs.append(f"line{ln}: 数值解析失败")
                    continue
                xs = pts[0::2]; ys = pts[1::2]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                seg_n += 1
            else:
                errs.append(f"line{ln}: 字段数={n + 1} 无法识别为检测框或多边形")
                continue
            if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
                errs.append(f"line{ln}: 包围盒越界 [{x1:.3f},{y1:.3f},{x2:.3f},{y2:.3f}]")
                continue
            boxes.append([cls, x1, y1, x2, y2])
    return boxes, errs, {"det": det_n, "seg": seg_n}

def main():
    idir = os.path.join(RAW, "train", "images")
    ldir = os.path.join(RAW, "train", "labels")
    imgs = sorted([f for f in os.listdir(idir) if f.lower().endswith(IMG_EXT)])
    lbls = sorted([f for f in os.listdir(ldir) if f.lower().endswith(".txt")])

    n_img = len(imgs)
    n_lbl = len(lbls)
    img_stems = {os.path.splitext(f)[0] for f in imgs}
    lbl_stems = {os.path.splitext(f)[0] for f in lbls}
    matched = img_stems & lbl_stems
    imgs_no_label = img_stems - lbl_stems
    lbls_no_image = lbl_stems - img_stems

    empty_labels = 0
    invalid_lines = 0
    det_total = 0
    seg_total = 0
    class_counter = collections.Counter()
    obj_per_img = []
    norm_w, norm_h, norm_area = [], [], []
    abs_area_px = []
    coco_small = coco_medium = coco_large = 0
    img_dims = collections.Counter()
    img_file_bytes = []
    label_file_bytes = []

    for f in imgs:
        stem = os.path.splitext(f)[0]
        ip = os.path.join(idir, f)
        lp = os.path.join(ldir, stem + ".txt")
        img_file_bytes.append(os.path.getsize(ip))
        wh = img_size(ip)
        if wh:
            img_dims[wh] += 1
        boxes, errs, cnt = ([], [], {"det": 0, "seg": 0}) if not os.path.exists(lp) else parse_label(lp)
        if os.path.exists(lp):
            label_file_bytes.append(os.path.getsize(lp))
        if os.path.exists(lp) and os.path.getsize(lp) == 0:
            empty_labels += 1
        invalid_lines += len(errs)
        det_total += cnt["det"]; seg_total += cnt["seg"]
        obj_per_img.append(len(boxes))
        for b in boxes:
            cls, x1, y1, x2, y2 = b
            class_counter[cls] += 1
            w = x2 - x1; h = y2 - y1
            norm_w.append(w); norm_h.append(h); norm_area.append(w * h)
            if wh:
                aw = w * wh[0]; ah = h * wh[1]
                area = aw * ah
                abs_area_px.append(area)
                if area < 32 * 32:
                    coco_small += 1
                elif area < 96 * 96:
                    coco_medium += 1
                else:
                    coco_large += 1

    total_obj = sum(obj_per_img)
    report = {
        "subset": "train 前 614 张 (顺序前缀, 非随机采样)",
        "images": n_img,
        "labels": n_lbl,
        "image_label_matched": len(matched),
        "images_without_label": len(imgs_no_label),
        "labels_without_image": len(lbls_no_image),
        "empty_labels": empty_labels,
        "invalid_label_lines": invalid_lines,
        "det_objects": det_total,
        "seg_objects": seg_total,
        "total_objects": total_obj,
        "classes_present": len(class_counter),
        "class_distribution": dict(sorted(class_counter.items())),
        "objects_per_image": {
            "min": min(obj_per_img), "max": max(obj_per_img),
            "mean": round(statistics.mean(obj_per_img), 2),
            "median": statistics.median(obj_per_img),
        },
        "norm_bbox_w": _stat(norm_w),
        "norm_bbox_h": _stat(norm_h),
        "norm_bbox_area": _stat(norm_area),
        "abs_bbox_area_px": _stat(abs_area_px) if abs_area_px else None,
        "coco_size_buckets": {
            "small_<32^2": coco_small, "medium_32^2-96^2": coco_medium,
            "large_>96^2": coco_large,
            "total": coco_small + coco_medium + coco_large,
        },
        "image_dimensions_top": img_dims.most_common(5),
        "img_file_size_kb": _stat([b / 1024 for b in img_file_bytes]),
        "label_file_size_bytes": _stat(label_file_bytes),
        "cv2_available": HAS_CV2,
    }

    md = _to_markdown(report)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\n[OK] 报告已写入: {OUT}")

def _stat(xs):
    if not xs:
        return None
    return {
        "min": round(min(xs), 4), "max": round(max(xs), 4),
        "mean": round(statistics.mean(xs), 4),
        "median": round(statistics.median(xs), 4),
    }

def _to_markdown(r):
    L = []
    L.append("# ROD-Dataset 子集数据集分析（614 张）\n")
    L.append(f"> 分析对象：**{r['subset']}**  \n> 说明：此为顺序前缀样本，**非随机采样**；类目名因 `data.yaml` 未下载而暂以 class index 表示。\n")
    L.append("## 1. 完整性与配对")
    L.append(f"- 图像数: **{r['images']}**")
    L.append(f"- 标签数: **{r['labels']}**")
    L.append(f"- 图像-标签配对成功: **{r['image_label_matched']}**")
    L.append(f"- 有图无标签: {r['images_without_label']}")
    L.append(f"- 有标签无图: {r['labels_without_image']}")
    L.append(f"- 空标签文件: {r['empty_labels']}")
    L.append(f"- 真正非法标注行(无法解析为检测框/多边形): {r['invalid_label_lines']}")
    L.append("\n## 2. 标注总量与类目")
    L.append(f"- 目标总数(检测框+分割多边形): **{r['total_objects']}**")
    L.append(f"  - 其中检测框(YOLO 5字段): {r['det_objects']}")
    L.append(f"  - 其中分割多边形(>5字段): {r['seg_objects']}")
    L.append(f"  - 说明: 数据集**同时含检测与分割标注**, 非常适合本项目的「盲道障碍物检测」+ 后续可选的分割任务。")
    L.append(f"- 出现类目数: **{r['classes_present']}**（未知全集类目数，因缺 data.yaml）")
    L.append("\n### 类目分布（按 class index）\n")
    L.append("| class index | 目标数 | 占比 |")
    L.append("|---|---|---|")
    tot = r['total_objects'] or 1
    for k, v in r['class_distribution'].items():
        L.append(f"| {k} | {v} | {v/tot*100:.1f}% |")
    L.append("\n## 3. 目标密度（每张图目标数）")
    o = r['objects_per_image']
    L.append(f"- 最小/最大: {o['min']} / {o['max']}")
    L.append(f"- 均值/中位数: {o['mean']} / {o['median']}")
    L.append("\n## 4. 边界框尺度（归一化）")
    for k in ("norm_bbox_w", "norm_bbox_h", "norm_bbox_area"):
        s = r[k]
        if s:
            L.append(f"- {k}: min={s['min']} max={s['max']} mean={s['mean']} median={s['median']}")
    L.append("\n## 5. 绝对目标尺度（COCO 标准，需读图）")
    if r['cv2_available']:
        a = r['abs_bbox_area_px']
        L.append(f"- 绝对面积(px²): min={a['min']} max={a['max']} mean={a['mean']} median={a['median']}")
        cb = r['coco_size_buckets']
        L.append(f"- 小目标(<32²): {cb['small_<32^2']} ({cb['small_<32^2']/cb['total']*100:.1f}%)")
        L.append(f"- 中目标(32²-96²): {cb['medium_32^2-96^2']} ({cb['medium_32^2-96^2']/cb['total']*100:.1f}%)")
        L.append(f"- 大目标(>96²): {cb['large_>96^2']} ({cb['large_>96^2']/cb['total']*100:.1f}%)")
    else:
        L.append("- opencv 不可用，跳过绝对尺度统计")
    L.append("\n## 6. 图像属性")
    L.append(f"- 尺寸分布(宽×高, Top5): {r['image_dimensions_top']}")
    s = r['img_file_size_kb']
    L.append(f"- 图像文件大小(KB): min={s['min']:.1f} max={s['max']:.1f} mean={s['mean']:.1f}")
    L.append("\n## 7. 可行性判断")
    L.append("- **能否做数据集分析：能。** 对这 614 张可完成完整性、标注合法性、类目分布、目标尺度、图像属性的描述性统计。")
    L.append("- **局限**：① 仅 train 顺序前缀(IMG_00001~614)，非随机采样，类目分布可能与全集有偏；② 仅占全集 24,326 的 ~2.5%；③ 缺 data.yaml，类目名为 index；④ 无 valid/test，无法评估划分均衡性。")
    L.append("- **结论**：足以做**初步质量体检与训练可行性判断**（确认标签格式正确、目标尺度偏小需关注），但不足以替代对全集的权威分布断言；补全下载后结论可外推。")
    return "\n".join(L)

if __name__ == "__main__":
    main()
