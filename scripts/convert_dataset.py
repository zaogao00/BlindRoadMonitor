#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 11 — 数据集转换: datasets/raw/** -> datasets/processed/ (YOLO **detection**)

设计依据: docs/dataset_analysis.md (Phase 10) 的 §6 类别方案 与 §8 转换清单。

核心原则
--------
1. **datasets/raw/** 严格只读 —— 不写入、不删除、不修改任何一个字节。
2. 输出 `datasets/processed/{images,labels}/{train,val,test}`。
3. 任务类型为 **detection**(非 seg): 盲道类只有 WOTR 的水平框, 无任何 mask/polygon 监督
   (详见报告 §2「分割可行性」), 因此 ROD 的多边形在此统一退化为外接矩形。
4. 类别统一为 **26 类**, 丢弃 ROD 的 `Building` / `Road` 两个背景类(按行整行剔除)。
5. 全局 MD5 去重: 同组按 test > val > train 的优先级保留 1 份, 消除划分泄漏。

用法
----
    python scripts/convert_dataset.py --dry-run     # 只统计, 不写盘
    python scripts/convert_dataset.py               # 执行转换
    python scripts/convert_dataset.py --force       # 输出目录非空时强制覆盖
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------- 路径常量
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = PROJECT_ROOT / "datasets" / "raw"
OUT_ROOT = PROJECT_ROOT / "datasets" / "processed"

WOTR_ROOT = RAW_ROOT / "wotr" / "WOTR"
ROD_ROOT = RAW_ROOT / "rod_dataset"

SPLITS = ("train", "val", "test")
# 去重保留优先级: 数字越小越优先保留 (val/test 比 train 更宝贵, 不能被污染)
SPLIT_PRIORITY = {"test": 0, "val": 1, "train": 2}

# ------------------------------------------------------- 统一 26 类类别体系
# 索引即 class id, 顺序与 data.yaml 的 names 一致
UNIFIED_CLASSES = [
    "blind_road",      # 0  核心类
    "person",          # 1
    "pole",            # 2
    "car",             # 3
    "tree",            # 4
    "motorcycle",      # 5
    "warning_column",  # 6
    "crosswalk",       # 7
    "bicycle",         # 8
    "green_light",     # 9
    "red_light",       # 10
    "roadblock",       # 11
    "cone",            # 12
    "truck",           # 13
    "sign",            # 14
    "trash_bin",       # 15
    "bus",             # 16
    "tricycle",        # 17
    "fire_hydrant",    # 18
    "dog",             # 19
    "stairs",          # 20
    "manhole",         # 21
    "guard_rail",      # 22
    "chair",           # 23
    "bench",           # 24
    "plant_pot",       # 25
]
CLASS_ID = {name: i for i, name in enumerate(UNIFIED_CLASSES)}

# WOTR (PASCAL-VOC, 20 类) -> 统一类
WOTR_MAP = {
    "blind_road": "blind_road",
    "person": "person",
    "pole": "pole",
    "car": "car",
    "tree": "tree",
    "motorcycle": "motorcycle",
    "warning_column": "warning_column",
    "crosswalk": "crosswalk",
    "bicycle": "bicycle",
    "green_light": "green_light",
    "red_light": "red_light",
    "roadblock": "roadblock",
    "reflective_cone": "cone",
    "truck": "truck",
    "sign": "sign",
    "ashcan": "trash_bin",
    "bus": "bus",
    "tricycle": "tricycle",
    "fire_hydrant": "fire_hydrant",
    "dog": "dog",
}

# ROD (YOLO 原生, 25 类) -> 统一类;  None = 明确丢弃(背景类)
ROD_MAP = {
    "Bike": "bicycle",
    "Bicycle Rack": "bicycle",
    "Building": None,              # 丢弃: 大背景建筑, 框巨大且边界模糊
    "Road": None,                  # 丢弃: 路面区域, 与 blind_road 语义冲突
    "Bus": "bus",
    "Car": "car",
    "Chair": "chair",
    "Dog": "dog",
    "Dustbin": "trash_bin",
    "Electrical Box": "pole",
    "Electrical Pole": "pole",
    "Fire hydrant": "fire_hydrant",
    "Guard rail": "guard_rail",
    "Manhole": "manhole",
    "Motorcycle": "motorcycle",
    "Pedestrian crosswalk": "crosswalk",
    "Person": "person",
    "Plant Pot": "plant_pot",
    "Stairs": "stairs",
    "Teraffic Barrel": "roadblock",
    "Traffic Cone": "cone",
    "Traffic sign": "sign",
    "Tree": "tree",
    "Truck": "truck",
    "Bench": "bench",
}

# 输出文件名前缀: 保证两数据集零冲突, 且可反查来源
SRC_PREFIX = {"wotr": "wotr_", "rod": "rod_"}


# ------------------------------------------------------------------ 数据结构
@dataclass
class Item:
    """一张待转换的图片及其转换后的 YOLO 标注行。"""

    src_img: Path
    src_label: Path | None
    source: str            # "wotr" | "rod"
    split: str             # train | val | test
    raw_stem: str
    lines: list[str] = field(default_factory=list)

    @property
    def dst_stem(self) -> str:
        return SRC_PREFIX[self.source] + self.raw_stem

    @property
    def n_objects(self) -> int:
        return len(self.lines)


# -------------------------------------------------------------------- 工具
def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def file_md5(path: Path, block: int = 1 << 20) -> str:
    """计算文件 MD5。注意: hash 对象必须在函数体内创建, 不可作默认参数。"""
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_line(cid: int, cx: float, cy: float, w: float, h: float) -> str:
    return f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


# --------------------------------------------------------------- 解析器: VOC
def parse_voc(xml_path: Path):
    """解析 PASCAL-VOC XML -> YOLO detection 行。

    返回 (lines, n_objects, n_dropped, unknown_names, img_w, img_h)

    两个必须遵守的坑 (见报告 §8.1):
      * 图片配对靠 **XML stem ↔ JPEGImages stem**, 绝不能用 XML 内的 <filename>
        (实测 13,926/13,928 不一致, 用了会转换出 0 条有效数据)。
      * 尺寸取 XML 的 <size>(Phase 10 已全量验证与实际图片 100% 一致)。
    """
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    img_w = int(float(size.findtext("width", "0")))
    img_h = int(float(size.findtext("height", "0")))
    if img_w <= 0 or img_h <= 0:
        raise ValueError(f"{xml_path.name}: 非法图片尺寸 {img_w}x{img_h}")

    lines, unknown = [], Counter()
    n_objects = n_dropped = 0

    for obj in root.findall("object"):
        name = (obj.findtext("name") or "").strip()
        n_objects += 1
        # WOTR 的 20 类全部保留, 但遇到未登记的类名必须报错而不是静默丢弃
        if name not in WOTR_MAP:
            unknown[name] += 1
            continue
        unified = WOTR_MAP[name]
        if unified is None:
            n_dropped += 1
            continue

        box = obj.find("bndbox")
        if box is None:
            n_dropped += 1
            continue
        x1 = float(box.findtext("xmin"))
        y1 = float(box.findtext("ymin"))
        x2 = float(box.findtext("xmax"))
        y2 = float(box.findtext("ymax"))
        if x2 <= x1 or y2 <= y1:
            n_dropped += 1
            continue

        cx = ((x1 + x2) / 2.0) / img_w
        cy = ((y1 + y2) / 2.0) / img_h
        bw = (x2 - x1) / img_w
        bh = (y2 - y1) / img_h
        lines.append(
            fmt_line(
                CLASS_ID[unified],
                clamp(cx), clamp(cy), clamp(bw), clamp(bh),
            )
        )
    return lines, n_objects, n_dropped, unknown, img_w, img_h


# --------------------------------------------------------------- 解析器: YOLO
def parse_yolo_txt(txt_path: Path):
    """解析 ROD 的 YOLO 标签(检测框与多边形混合) -> 统一 YOLO detection 行。

    返回 (lines, n_objects, n_dropped, n_polygon, unknown_names)

    处理规则 (见报告 §8.2):
      * 5 列  -> 标准检测框, 坐标已归一化, 直接重映射类 id。
      * >5 列 -> 多边形分割, 取 x/y 的 min/max 退化为外接矩形。
      * `Building` / `Road` -> 整行删除(计数进 n_dropped)。
    """
    lines, unknown = [], Counter()
    n_objects = n_polygon = n_dropped = 0

    text = txt_path.read_text(encoding="utf-8").strip()
    if not text:
        return lines, 0, 0, 0, unknown          # 空标签 -> 负样本, 原样保留

    for raw in text.splitlines():
        parts = raw.split()
        if not parts:
            continue
        n_objects += 1
        try:
            cid = int(float(parts[0]))
            coords = [float(x) for x in parts[1:]]
        except ValueError:
            n_dropped += 1
            continue

        if cid < 0 or cid >= len(ROD_NAMES):
            unknown[f"<id:{cid}>"] += 1
            continue
        name = ROD_NAMES[cid]
        unified = ROD_MAP.get(name)
        if unified is None:
            # 未登记 或 明确丢弃的背景类
            n_dropped += 1
            if name not in ROD_MAP:
                unknown[name] += 1
            continue

        if len(coords) >= 6 and len(coords) % 2 == 0:
            # 多边形: 取外接矩形
            n_polygon += 1
            xs = coords[0::2]
            ys = coords[1::2]
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            bw, bh = x2 - x1, y2 - y1
        elif len(coords) == 4:
            cx, cy, bw, bh = coords
        else:
            n_dropped += 1
            continue

        if bw <= 0 or bh <= 0:
            n_dropped += 1
            continue
        lines.append(
            fmt_line(
                CLASS_ID[unified],
                clamp(cx), clamp(cy), clamp(bw), clamp(bh),
            )
        )
    return lines, n_objects, n_dropped, n_polygon, unknown


# ------------------------------------------------------------- 扫描: WOTR
def scan_wotr() -> tuple[list[Item], dict]:
    """扫描 WOTR。划分来自 ImageSets/Main/{train,val,test}.txt。"""
    stats = {
        "n_images": 0, "n_objects": 0, "n_dropped": 0,
        "unknown": Counter(), "missing_image": [], "missing_xml": [],
    }
    # 划分表: stem -> split
    split_of: dict[str, str] = {}
    for sp in SPLITS:
        f = WOTR_ROOT / "ImageSets" / "Main" / f"{sp}.txt"
        for line in f.read_text(encoding="utf-8").splitlines():
            stem = line.strip()
            if stem:
                split_of[stem] = sp

    img_dir = WOTR_ROOT / "JPEGImages"
    ann_dir = WOTR_ROOT / "Annotations"

    img_stems = {p.stem: p for p in img_dir.iterdir() if p.is_file()}
    xml_stems = {p.stem: p for p in ann_dir.iterdir() if p.suffix.lower() == ".xml"}

    stats["missing_xml"] = sorted(set(img_stems) - set(xml_stems))
    stats["missing_image"] = sorted(set(xml_stems) - set(img_stems))

    items: list[Item] = []
    for stem in sorted(set(img_stems) & set(xml_stems)):
        sp = split_of.get(stem)
        if sp is None:
            stats["missing_xml"].append(f"{stem} (无划分归属)")
            continue
        lines, n_obj, n_drop, unknown, _, _ = parse_voc(xml_stems[stem])
        stats["n_objects"] += n_obj
        stats["n_dropped"] += n_drop
        stats["unknown"].update(unknown)
        stats["n_images"] += 1
        items.append(
            Item(
                src_img=img_stems[stem],
                src_label=xml_stems[stem],
                source="wotr",
                split=sp,
                raw_stem=stem,
                lines=lines,
            )
        )
    return items, stats


# --------------------------------------------------------------- 扫描: ROD
def scan_rod() -> tuple[list[Item], dict]:
    """扫描 ROD。划分来自目录名 train/valid/test, 其中 valid 映射到 val。"""
    stats = {
        "n_images": 0, "n_objects": 0, "n_dropped": 0, "n_polygon": 0,
        "unknown": Counter(), "missing_image": [], "missing_xml": [],
    }
    dir_split = {"train": "train", "valid": "val", "test": "test"}

    items: list[Item] = []
    for dirname, sp in dir_split.items():
        img_dir = ROD_ROOT / dirname / "images"
        lbl_dir = ROD_ROOT / dirname / "labels"
        if not img_dir.is_dir():
            continue
        for img_path in sorted(img_dir.iterdir()):
            if not img_path.is_file():
                continue
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            if not lbl_path.is_file():
                stats["missing_xml"].append(str(lbl_path.relative_to(RAW_ROOT)))
                continue
            lines, n_obj, n_drop, n_poly, unknown = parse_yolo_txt(lbl_path)
            stats["n_objects"] += n_obj
            stats["n_dropped"] += n_drop
            stats["n_polygon"] += n_poly
            stats["unknown"].update(unknown)
            stats["n_images"] += 1
            items.append(
                Item(
                    src_img=img_path,
                    src_label=lbl_path,
                    source="rod",
                    split=sp,
                    raw_stem=img_path.stem,
                    lines=lines,
                )
            )
    return items, stats


# ----------------------------------------------------------------- 全局去重
def dedupe(items: list[Item]) -> tuple[list[Item], list[Item]]:
    """按 MD5 全局去重。同组保留 split 优先级最高(test>val>train)的一份。

    先按文件大小分桶, 只对同大小的组计算 MD5, 大幅减少 IO。
    返回 (保留项, 被剔除项)。
    """
    by_size: dict[int, list[Item]] = defaultdict(list)
    for it in items:
        by_size[it.src_img.stat().st_size].append(it)

    groups: dict[str, list[Item]] = defaultdict(list)
    for group in by_size.values():
        if len(group) == 1:
            continue                       # 大小唯一 -> 不可能重复
        for it in group:
            groups[file_md5(it.src_img)].append(it)

    removed: set[int] = set()
    dup_groups: list[list[Item]] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda x: (SPLIT_PRIORITY[x.split], x.dst_stem))
        dup_groups.append(members)
        for loser in members[1:]:
            removed.add(id(loser))

    kept = [it for it in items if id(it) not in removed]
    dropped = [it for it in items if id(it) in removed]
    return kept, dropped


# ------------------------------------------------------------------- 写出
def write_out(items: list[Item], stats: dict) -> None:
    for sp in SPLITS:
        (OUT_ROOT / "images" / sp).mkdir(parents=True, exist_ok=True)
        (OUT_ROOT / "labels" / sp).mkdir(parents=True, exist_ok=True)

    per_split_img = Counter()
    per_split_obj = Counter()
    per_split_empty = Counter()
    class_counter = Counter()
    class_by_split = defaultdict(Counter)
    copied_bytes = 0

    for it in items:
        dst_img = OUT_ROOT / "images" / it.split / f"{it.dst_stem}{it.src_img.suffix.lower()}"
        dst_lbl = OUT_ROOT / "labels" / it.split / f"{it.dst_stem}.txt"

        shutil.copy2(it.src_img, dst_img)          # raw 只读, 这里只是读出
        copied_bytes += it.src_img.stat().st_size

        dst_lbl.write_text(
            "\n".join(it.lines) + ("\n" if it.lines else ""),
            encoding="utf-8",
        )

        per_split_img[it.split] += 1
        per_split_obj[it.split] += it.n_objects
        if not it.lines:
            per_split_empty[it.split] += 1
        for line in it.lines:
            cid = int(line.split()[0])
            class_counter[cid] += 1
            class_by_split[cid][it.split] += 1

    stats["out_per_split_images"] = dict(per_split_img)
    stats["out_per_split_objects"] = dict(per_split_obj)
    stats["out_per_split_empty"] = dict(per_split_empty)
    stats["out_copied_bytes"] = copied_bytes
    stats["out_class_instances"] = {
        UNIFIED_CLASSES[c]: class_counter[c] for c in sorted(class_counter)
    }
    stats["out_class_by_split"] = {
        UNIFIED_CLASSES[c]: dict(class_by_split[c]) for c in sorted(class_by_split)
    }


# ------------------------------------------------------------- data.yaml
def write_data_yaml() -> Path:
    """生成统一 data.yaml (YOLO detection)。

    path 使用**绝对路径 + 正斜杠**: Windows 反斜杠在 YAML 里需转义, 且训练时
    当前工作目录可能不在项目根, 绝对路径可避免 cwd 依赖。
    """
    posix_root = str(OUT_ROOT).replace("\\", "/")
    lines = [
        "# Phase 11 — 统一 YOLO detection 数据集",
        "# 来源: WOTR (PASCAL-VOC, 20 类) + ROD-Dataset (YOLO 原生, 25 类)",
        "# 转换脚本: scripts/convert_dataset.py  (datasets/raw/** 严格只读)",
        "# 任务类型: detect — 盲道类无任何 mask/polygon 监督, 不做 segmentation",
        f"# 类别: {len(UNIFIED_CLASSES)}  (已丢弃 ROD 的 Building / Road 两个背景类)",
        "",
        f"path: {posix_root}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "",
        f"nc: {len(UNIFIED_CLASSES)}",
        "names: [" + ", ".join(f"'{n}'" for n in UNIFIED_CLASSES) + "]",
        "",
        "# 类别来源对照 (WOTR -> ROD):",
        "#   0  blind_road   <- WOTR blind_road                    [核心类]",
        "#   2  pole         <- WOTR pole | ROD 'Electrical Pole','Electrical Box'",
        "#   8  bicycle      <- WOTR bicycle | ROD 'Bike','Bicycle Rack'",
        "#   12 cone         <- WOTR reflective_cone | ROD 'Traffic Cone'",
        "#   15 trash_bin    <- WOTR ashcan | ROD 'Dustbin'",
        "",
    ]
    out = OUT_ROOT / "data.yaml"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# -------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 11: raw -> processed (YOLO detection)")
    ap.add_argument("--dry-run", action="store_true", help="只统计, 不写盘")
    ap.add_argument("--force", action="store_true", help="输出目录非空时仍继续(覆盖同名文件)")
    args = ap.parse_args()

    if not WOTR_ROOT.is_dir() or not ROD_ROOT.is_dir():
        print(f"[FATAL] 找不到原始数据: {WOTR_ROOT} 或 {ROD_ROOT}")
        return 2

    if OUT_ROOT.exists() and any(OUT_ROOT.iterdir()) and not args.force and not args.dry_run:
        print(f"[FATAL] 输出目录非空: {OUT_ROOT}\n"
              f"        为避免半旧半新的混合状态, 请先用 --force 或手动清空后重跑。")
        return 2

    # ROD 的类名表(供 parse_yolo_txt 按 id 反查)
    global ROD_NAMES
    ROD_NAMES = load_rod_names()

    print("=" * 72)
    print("Phase 11 — 数据集转换 (YOLO detection)")
    print("=" * 72)
    print(f"源 (只读): {RAW_ROOT}")
    print(f"目标     : {OUT_ROOT}")
    print(f"模式     : {'DRY-RUN (不写盘)' if args.dry_run else 'EXECUTE'}")
    print(f"类别体系 : {len(UNIFIED_CLASSES)} 类 (核心类 blind_road = id 0)")
    print("-" * 72)

    wotr_items, w_stats = scan_wotr()
    rod_items, r_stats = scan_rod()
    all_items = wotr_items + rod_items

    print(f"扫描 WOTR: {w_stats['n_images']:>6} 图 / {w_stats['n_objects']:>7} 实例")
    print(f"扫描 ROD : {r_stats['n_images']:>6} 图 / {r_stats['n_objects']:>7} 实例"
          f" (含多边形 {r_stats['n_polygon']})")
    print(f"合计     : {len(all_items):>6} 图")
    print("-" * 72)

    kept, dropped = dedupe(all_items)
    drop_by_split = Counter(it.split for it in dropped)
    drop_by_source = Counter(it.source for it in dropped)
    print(f"去重     : 剔除 {len(dropped)} 张重复图"
          f" (按 split: {dict(drop_by_split)}; 按来源: {dict(drop_by_source)})")
    print(f"保留     : {len(kept)} 张")
    print("-" * 72)

    stats = {
        "task": "detect",
        "n_classes": len(UNIFIED_CLASSES),
        "classes": UNIFIED_CLASSES,
        "wotr": {
            "scanned_images": w_stats["n_images"],
            "scanned_objects": w_stats["n_objects"],
            "dropped_objects": w_stats["n_dropped"],
            "missing_xml": w_stats["missing_xml"],
            "missing_image": w_stats["missing_image"],
            "unknown_classes": dict(w_stats["unknown"]),
        },
        "rod": {
            "scanned_images": r_stats["n_images"],
            "scanned_objects": r_stats["n_objects"],
            "dropped_objects": r_stats["n_dropped"],
            "polygons": r_stats["n_polygon"],
            "missing_label": r_stats["missing_xml"],
            "unknown_classes": dict(r_stats["unknown"]),
        },
        "dedupe": {
            "removed_images": len(dropped),
            "removed_by_split": dict(drop_by_split),
            "removed_by_source": dict(drop_by_source),
            "removed_files": [
                {"source": it.source, "split": it.split, "file": it.src_img.name}
                for it in sorted(dropped, key=lambda x: (x.source, x.split, x.src_img.name))
            ],
        },
        "kept_images": len(kept),
    }

    if args.dry_run:
        print("\n[DRY-RUN] 未写盘。以下为预期输出:")
    else:
        write_out(kept, stats)
        print("\n[EXECUTE] 写出完成:")
        print(f"  data.yaml: {write_data_yaml()}")

    if not args.dry_run:
        for sp in SPLITS:
            print(f"  {sp:<5}: images={stats['out_per_split_images'].get(sp, 0):>6}"
                  f"  labels={stats['out_per_split_images'].get(sp, 0):>6}"
                  f"  实例={stats['out_per_split_objects'].get(sp, 0):>7}"
                  f"  空标签={stats['out_per_split_empty'].get(sp, 0)}")
        total_obj = sum(stats["out_per_split_objects"].values())
        print(f"  {'合计':<5}: images={len(kept):>6}  实例={total_obj:>7}"
              f"  占用={stats['out_copied_bytes'] / 2**30:.3f} GiB")

    # 未登记类名 -> 必须为空, 否则说明映射表漏类(会导致静默丢数据)
    unknown_all = {**w_stats["unknown"], **r_stats["unknown"]}
    if unknown_all:
        print("\n[FATAL] 发现未登记的类别名, 映射表不完整:")
        for k, v in unknown_all.items():
            print(f"        {k}: {v}")
        return 3

    print("\n[OK] 所有类别均已映射, 无静默丢类。")

    # 写报告
    report_path = PROJECT_ROOT / "docs" / "phase11_conversion_report.json"
    stats["dropped_classes"] = ["Building", "Road"]
    report_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] 转换报告: {report_path.relative_to(PROJECT_ROOT)}")
    return 0


def load_rod_names() -> list[str]:
    """读取 ROD 的 data.yaml 里的 25 个类名(顺序即原始 class id)。"""
    yml = (ROD_ROOT / "data.yaml").read_text(encoding="utf-8")
    for line in yml.splitlines():
        if line.strip().startswith("names:"):
            inner = line.split(":", 1)[1].strip()
            return [x.strip().strip("'\"") for x in inner.strip("[]").split(",")]
    raise RuntimeError("ROD data.yaml 中找不到 names 字段")


ROD_NAMES: list[str] = []


if __name__ == "__main__":
    raise SystemExit(main())
