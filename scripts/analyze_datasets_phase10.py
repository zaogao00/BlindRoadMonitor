"""
Phase 10 — 数据集结构与标签分析（**只读**，不修改 / 不删除任何原始数据）

分析对象:
  1. WOTR  (datasets/raw/wotr/WOTR)        — PASCAL-VOC (XML + bndbox)
  2. ROD   (datasets/raw/rod_dataset)      — YOLO 原生 (txt, 检测框 + 分割多边形混合)

统计项: 图片数 / 标签数 / 分辨率 / 类别数与名称 / 标注格式 / 划分 / 损坏图 / 空标签 / 重复图
输出: docs/dataset_analysis_stats.json (供 docs/dataset_analysis.md 引用)
"""

import sys
import os
import json
import hashlib
import collections
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
WOTR = ROOT / "datasets" / "raw" / "wotr" / "WOTR"
ROD = ROOT / "datasets" / "raw" / "rod_dataset"
OUT = ROOT / "docs" / "dataset_analysis_stats.json"

try:
    from PIL import Image

    PIL_OK = True
except Exception:  # pragma: no cover
    PIL_OK = False

# COCO 尺度定义（按 bbox 像素面积）
SMALL, MEDIUM = 32 * 32, 96 * 96


def md5_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def coco_scale(area: float) -> str:
    if area < SMALL:
        return "small"
    if area < MEDIUM:
        return "medium"
    return "large"


def summarize_resolutions(sizes):
    """sizes: list[(w, h)]"""
    if not sizes:
        return {}
    ws = [w for w, _ in sizes]
    hs = [h for _, h in sizes]
    common = collections.Counter(sizes).most_common(8)
    ratios = [w / h for w, h in sizes]
    return {
        "width": {"min": min(ws), "max": max(ws), "mean": round(statistics.mean(ws), 1),
                  "median": statistics.median(ws)},
        "height": {"min": min(hs), "max": max(hs), "mean": round(statistics.mean(hs), 1),
                   "median": statistics.median(hs)},
        "aspect_ratio": {"min": round(min(ratios), 3), "max": round(max(ratios), 3),
                         "mean": round(statistics.mean(ratios), 3)},
        "megapixels_mean": round(statistics.mean(w * h for w, h in sizes) / 1e6, 3),
        "top_resolutions": [{"size": f"{w}x{h}", "count": c} for (w, h), c in common],
        "distinct_resolutions": len(set(sizes)),
    }


# ----------------------------------------------------------------------------- WOTR
def analyze_wotr():
    img_dir = WOTR / "JPEGImages"
    ann_dir = WOTR / "Annotations"
    sets_dir = WOTR / "ImageSets" / "Main"

    res = {
        "path": str(WOTR.relative_to(ROOT)).replace("\\", "/"),
        "format": "PASCAL-VOC (XML, axis-aligned bndbox)",
        "splits_source": "ImageSets/Main/{train,val,test}.txt",
    }

    # ---- 划分
    splits = {}
    for sp in ("train", "val", "test"):
        p = sets_dir / f"{sp}.txt"
        if p.exists():
            lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            splits[sp] = lines
    res["splits_declared"] = {k: len(v) for k, v in splits.items()}
    stem2split = {}
    for sp, names in splits.items():
        for n in names:
            stem2split[n] = sp

    images = sorted(img_dir.iterdir())
    res["image_count"] = len(images)

    hashes = collections.defaultdict(list)
    sizes = []
    corrupt = []
    zero_byte = []
    exts = collections.Counter()
    cls_inst = collections.Counter()
    cls_imgs = collections.defaultdict(set)
    cls_split = collections.defaultdict(collections.Counter)
    empty_labels = []
    missing_xml = []
    scale = collections.Counter()
    scale_cls_small = collections.Counter()
    obj_areas = []
    objs_per_img = []
    invalid_box = 0
    out_of_bounds = 0
    truncated = 0
    difficult = 0
    total_objs = 0
    declared_sizes_mismatch = 0

    for i, img in enumerate(images):
        stem = img.stem
        exts[img.suffix.lower()] += 1
        if img.stat().st_size == 0:
            zero_byte.append(img.name)
            continue

        # ---- 图像解码校验 + 分辨率
        w = h = None
        if PIL_OK:
            try:
                with Image.open(img) as im:
                    im.verify()
                with Image.open(img) as im:
                    w, h = im.size
            except Exception as e:
                corrupt.append({"file": img.name, "error": type(e).__name__})
                continue
        if w and h:
            sizes.append((w, h))
        hashes[md5_of(img)].append(img.name)

        # ---- 标注
        xml = ann_dir / f"{stem}.xml"
        if not xml.exists():
            missing_xml.append(stem)
            continue
        try:
            root = ET.parse(xml).getroot()
        except Exception as e:
            corrupt.append({"file": xml.name, "error": f"XML parse: {type(e).__name__}"})
            continue

        sz = root.find("size")
        dw = int(float(sz.findtext("width") or 0))
        dh = int(float(sz.findtext("height") or 0))
        if w and h and (dw, dh) != (w, h):
            declared_sizes_mismatch += 1

        objs = root.findall("object")
        objs_per_img.append(len(objs))
        if not objs:
            empty_labels.append(stem)
        sp = stem2split.get(stem, "unassigned")
        for o in objs:
            total_objs += 1
            name = (o.findtext("name") or "").strip()
            cls_inst[name] += 1
            cls_imgs[name].add(stem)
            cls_split[name][sp] += 1
            if (o.findtext("truncated") or "0").strip() == "1":
                truncated += 1
            if (o.findtext("difficult") or "0").strip() == "1":
                difficult += 1
            b = o.find("bndbox")
            if b is None:
                invalid_box += 1
                continue
            x1 = float(b.findtext("xmin"))
            y1 = float(b.findtext("ymin"))
            x2 = float(b.findtext("xmax"))
            y2 = float(b.findtext("ymax"))
            if x2 <= x1 or y2 <= y1:
                invalid_box += 1
                continue
            if x1 < 0 or y1 < 0 or (dw and x2 > dw) or (dh and y2 > dh):
                out_of_bounds += 1
            bw, bh = x2 - x1, y2 - y1
            area = bw * bh
            obj_areas.append(area)
            s = coco_scale(area)
            scale[s] += 1
            if s == "small":
                scale_cls_small[name] += 1

    res["label_file_count"] = len(list(ann_dir.glob("*.xml")))
    res["extensions"] = dict(exts)
    res["corrupt_images"] = corrupt
    res["corrupt_count"] = len(corrupt)
    res["zero_byte_images"] = zero_byte
    res["missing_label_for_image"] = missing_xml
    res["resolution"] = summarize_resolutions(sizes)
    res["empty_labels"] = {"count": len(empty_labels), "samples": empty_labels[:20]}
    res["objects_total"] = total_objs
    res["objects_per_image"] = {
        "mean": round(statistics.mean(objs_per_img), 2) if objs_per_img else 0,
        "max": max(objs_per_img) if objs_per_img else 0,
        "min": min(objs_per_img) if objs_per_img else 0,
    }
    res["classes"] = {
        "count": len(cls_inst),
        "names": [k for k, _ in cls_inst.most_common()],
        "instances": dict(cls_inst.most_common()),
        "images_per_class": {k: len(v) for k, v in
                             sorted(cls_imgs.items(), key=lambda kv: -len(kv[1]))},
        "instances_by_split": {k: dict(v) for k, v in
                               sorted(cls_inst and cls_split.items(),
                                      key=lambda kv: -sum(kv[1].values()))},
    }
    res["bbox_scale_coco"] = dict(scale)
    res["bbox_scale_small_by_class"] = dict(scale_cls_small.most_common())
    res["bbox_area_px"] = {
        "median": round(statistics.median(obj_areas), 1) if obj_areas else 0,
        "mean": round(statistics.mean(obj_areas), 1) if obj_areas else 0,
        "p95": round(sorted(obj_areas)[int(len(obj_areas) * 0.95)], 1) if obj_areas else 0,
    }
    res["quality_flags"] = {
        "invalid_bbox": invalid_box,
        "out_of_bounds_bbox": out_of_bounds,
        "truncated_objects": truncated,
        "difficult_objects": difficult,
        "xml_size_vs_image_mismatch": declared_sizes_mismatch,
    }
    res["images_without_split_assignment"] = sum(
        1 for s in images if s.stem not in stem2split
    )

    dup = {h: names for h, names in hashes.items() if len(names) > 1}
    res["duplicate_images"] = {
        "groups": len(dup),
        "extra_files": sum(len(v) - 1 for v in dup.values()),
        "samples": [v for v in list(dup.values())[:10]],
    }
    res["_hashes"] = set(hashes.keys())
    return res


# ------------------------------------------------------------------------------ ROD
def analyze_rod():
    res = {
        "path": str(ROD.relative_to(ROOT)).replace("\\", "/"),
        "format": "YOLO native (txt: 5-col bbox + >5-col polygon seg, mixed)",
        "splits_source": "directory layout {train,valid,test}/images",
    }

    # class names from data.yaml (fallback: index only)
    names = []
    yaml = ROD / "data.yaml"
    nc = None
    if yaml.exists():
        txt = yaml.read_text(encoding="utf-8")
        for line in txt.splitlines():
            if line.strip().startswith("nc:"):
                nc = int(line.split(":", 1)[1].strip())
            if line.strip().startswith("names:"):
                inner = line.split(":", 1)[1]
                names = [x.strip().strip("'\"")
                         for x in inner.strip().strip("[]").split(",") if x.strip()]
    res["data_yaml"] = {"nc": nc, "names": names}

    hashes = collections.defaultdict(list)
    sizes = []
    corrupt = []
    zero_byte = []
    exts = collections.Counter()
    cls_inst = collections.Counter()
    cls_imgs = collections.defaultdict(set)
    cls_split = collections.defaultdict(collections.Counter)
    det_lines = seg_lines = invalid_lines = 0
    det_imgs = set()
    seg_imgs = set()
    empty_labels = []
    missing_labels = []
    scale = collections.Counter()
    scale_cls_small = collections.Counter()
    obj_areas = []
    objs_per_img = []
    cls_out_of_range = collections.Counter()
    coord_out_of_range = 0
    split_stats = {}

    for sp, folder in (("train", "train"), ("val", "valid"), ("test", "test")):
        img_dir = ROD / folder / "images"
        lbl_dir = ROD / folder / "labels"
        if not img_dir.exists():
            continue
        imgs = sorted(img_dir.iterdir())
        split_stats[sp] = {"images": len(imgs), "labels": len(list(lbl_dir.glob("*.txt")))
                           if lbl_dir.exists() else 0}
        for img in imgs:
            exts[img.suffix.lower()] += 1
            if img.stat().st_size == 0:
                zero_byte.append(img.name)
                continue
            w = h = None
            if PIL_OK:
                try:
                    with Image.open(img) as im:
                        im.verify()
                    with Image.open(img) as im:
                        w, h = im.size
                except Exception as e:
                    corrupt.append({"file": img.name, "error": type(e).__name__})
                    continue
            if w and h:
                sizes.append((w, h))
            hashes[md5_of(img)].append(f"{folder}/{img.name}")

            lbl = lbl_dir / f"{img.stem}.txt"
            if not lbl.exists():
                missing_labels.append(f"{folder}/{img.stem}")
                continue
            raw = [l.strip() for l in lbl.read_text(encoding="utf-8").splitlines() if l.strip()]
            if not raw:
                empty_labels.append(f"{folder}/{img.stem}")
            objs_per_img.append(len(raw))
            for line in raw:
                parts = line.split()
                try:
                    cid = int(float(parts[0]))
                    nums = [float(x) for x in parts[1:]]
                except Exception:
                    invalid_lines += 1
                    continue
                if nc is not None and not (0 <= cid < nc):
                    cls_out_of_range[cid] += 1
                    continue
                name = names[cid] if cid < len(names) else str(cid)
                cls_inst[name] += 1
                cls_imgs[name].add(f"{folder}/{img.stem}")
                cls_split[name][sp] += 1
                if len(nums) == 4:
                    det_lines += 1
                    det_imgs.add(f"{folder}/{img.stem}")
                    _, _, bw, bh = nums
                    if w and h:
                        area = (bw * w) * (bh * h)
                        obj_areas.append(area)
                        s = coco_scale(area)
                        scale[s] += 1
                        if s == "small":
                            scale_cls_small[name] += 1
                    if min(nums) < -0.001 or max(nums) > 1.001:
                        coord_out_of_range += 1
                elif len(nums) >= 6 and len(nums) % 2 == 0:
                    seg_lines += 1
                    seg_imgs.add(f"{folder}/{img.stem}")
                    xs = nums[0::2]
                    ys = nums[1::2]
                    if w and h:
                        area = (max(xs) - min(xs)) * w * (max(ys) - min(ys)) * h
                        obj_areas.append(area)
                        s = coco_scale(area)
                        scale[s] += 1
                        if s == "small":
                            scale_cls_small[name] += 1
                    if min(nums) < -0.001 or max(nums) > 1.001:
                        coord_out_of_range += 1
                else:
                    invalid_lines += 1

    total_imgs = sum(v["images"] for v in split_stats.values())
    res["image_count"] = total_imgs
    res["label_file_count"] = sum(v["labels"] for v in split_stats.values())
    res["splits"] = split_stats
    res["extensions"] = dict(exts)
    res["corrupt_images"] = corrupt
    res["corrupt_count"] = len(corrupt)
    res["zero_byte_images"] = zero_byte
    res["missing_label_for_image"] = missing_labels
    res["resolution"] = summarize_resolutions(sizes)
    res["empty_labels"] = {"count": len(empty_labels), "samples": empty_labels[:20]}
    res["annotation_lines"] = {
        "detection_bbox": det_lines,
        "segmentation_polygon": seg_lines,
        "invalid": invalid_lines,
        "images_with_detection": len(det_imgs),
        "images_with_segmentation": len(seg_imgs),
    }
    res["objects_total"] = det_lines + seg_lines
    res["objects_per_image"] = {
        "mean": round(statistics.mean(objs_per_img), 2) if objs_per_img else 0,
        "max": max(objs_per_img) if objs_per_img else 0,
        "min": min(objs_per_img) if objs_per_img else 0,
    }
    res["classes"] = {
        "count_declared": nc,
        "count_present": len(cls_inst),
        "names_declared": names,
        "names_present": [k for k, _ in cls_inst.most_common()],
        "instances": dict(cls_inst.most_common()),
        "images_per_class": {k: len(v) for k, v in
                             sorted(cls_imgs.items(), key=lambda kv: -len(kv[1]))},
        "instances_by_split": {k: dict(v) for k, v in
                               sorted(cls_split.items(), key=lambda kv: -sum(kv[1].values()))},
        "missing_from_sample": [n for n in names if n not in cls_inst],
    }
    res["bbox_scale_coco"] = dict(scale)
    res["bbox_scale_small_by_class"] = dict(scale_cls_small.most_common())
    res["bbox_area_px"] = {
        "median": round(statistics.median(obj_areas), 1) if obj_areas else 0,
        "mean": round(statistics.mean(obj_areas), 1) if obj_areas else 0,
        "p95": round(sorted(obj_areas)[int(len(obj_areas) * 0.95)], 1) if obj_areas else 0,
    }
    res["quality_flags"] = {
        "class_id_out_of_range": dict(cls_out_of_range),
        "coords_out_of_0_1": coord_out_of_range,
        "invalid_lines": invalid_lines,
    }
    dup = {h: names_ for h, names_ in hashes.items() if len(names_) > 1}
    res["duplicate_images"] = {
        "groups": len(dup),
        "extra_files": sum(len(v) - 1 for v in dup.values()),
        "samples": [v for v in list(dup.values())[:10]],
    }
    res["_hashes"] = set(hashes.keys())
    return res


def main():
    assert WOTR.exists(), f"missing {WOTR}"
    assert ROD.exists(), f"missing {ROD}"
    print("[Phase 10] analyzing WOTR ...", flush=True)
    wotr = analyze_wotr()
    print("[Phase 10] analyzing ROD ...", flush=True)
    rod = analyze_rod()

    cross = wotr.pop("_hashes") & rod.pop("_hashes")
    out = {
        "generated_by": "scripts/analyze_datasets_phase10.py (read-only)",
        "datasets": {"wotr": wotr, "rod": rod},
        "cross_dataset_duplicates": len(cross),
        "pil_available": PIL_OK,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # 控制台摘要
    for key, ds in (("WOTR", wotr), ("ROD", rod)):
        print(f"\n===== {key} =====")
        print(f"  images={ds['image_count']}  labels={ds['label_file_count']}")
        print(f"  corrupt={ds['corrupt_count']}  zero_byte={len(ds['zero_byte_images'])}")
        print(f"  empty_labels={ds['empty_labels']['count']}")
        print(f"  dup_groups={ds['duplicate_images']['groups']} "
              f"extra={ds['duplicate_images']['extra_files']}")
        r = ds["resolution"]
        print(f"  resolution: {r['width']['min']}x{r['height']['min']} ~ "
              f"{r['width']['max']}x{r['height']['max']}, mean "
              f"{r['width']['mean']}x{r['height']['mean']}, distinct={r['distinct_resolutions']}")
        print(f"  top: {r['top_resolutions'][:3]}")
        ncls = ds["classes"].get("count", ds["classes"].get("count_present"))
        print(f"  classes={ncls}  objects={ds['objects_total']}")
        print(f"  objects/image mean={ds['objects_per_image']['mean']}")
        print(f"  coco scale={ds['bbox_scale_coco']}")
    print(f"\ncross-dataset duplicates: {out['cross_dataset_duplicates']}")
    print(f"\nJSON -> {OUT}")


if __name__ == "__main__":
    main()
