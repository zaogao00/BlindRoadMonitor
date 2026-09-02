#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 11 — 转换后自检: 校验 datasets/processed/ 是否符合 YOLO detection 规范。

检查项
------
 1. 目录结构        images/{train,val,test} + labels/{train,val,test}
 2. 图片/标签数量   每个划分内必须一一对应 (stem 完全匹配)
 3. 图片完整性      PIL 全量 verify (损坏 / 零字节)
 4. 标签格式        每行必须 5 个字段, 且可解析为 float
 5. 类别 ID        必须 ∈ [0, nc-1]
 6. 坐标合法性      cx,cy,w,h ∈ [0,1] 且 w,h > 0
 7. 空标签          单独统计 (Ultralytics 视为背景负样本, 合法)
 8. 统计            每划分图片数/实例数, 每类实例数, 前缀分布
 9. 划分泄漏复查    全局 MD5, 跨划分重复必须为 0
10. data.yaml       nc / names / path 三项与实际一致

用法
----
    python scripts/check_dataset.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROC_ROOT = PROJECT_ROOT / "datasets" / "processed"
SPLITS = ("train", "val", "test")

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def file_md5(path: Path, block: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def load_yaml_names(yaml_path: Path):
    """极简 YAML 解析: 只取 nc / names / path 三个键。"""
    nc = None
    names: list[str] = []
    path_val = None
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("nc:"):
            nc = int(s.split(":", 1)[1].strip())
        elif s.startswith("names:"):
            inner = s.split(":", 1)[1].strip()
            names = [x.strip().strip("'\"") for x in inner.strip("[]").split(",")]
        elif s.startswith("path:"):
            path_val = s.split(":", 1)[1].strip().strip("'\"")
    return nc, names, path_val


def main() -> int:
    print("=" * 72)
    print("Phase 11 — 转换后自检 (YOLO detection)")
    print("=" * 72)

    if not PROC_ROOT.is_dir():
        print(f"[FATAL] 找不到 processed 目录: {PROC_ROOT}")
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    # ---------------------------------------------------------- 1. data.yaml
    yaml_path = PROC_ROOT / "data.yaml"
    nc, names, path_val = (None, [], None)
    if not yaml_path.is_file():
        errors.append("缺少 data.yaml")
    else:
        nc, names, path_val = load_yaml_names(yaml_path)
        print(f"data.yaml: nc={nc}  names={len(names)}  path={path_val}")

    # ------------------------------------------------------- 2. 逐划分扫描
    per_split_img: Counter = Counter()
    per_split_lbl: Counter = Counter()
    per_split_obj: Counter = Counter()
    per_split_empty: Counter = Counter()
    class_counter: Counter = Counter()
    class_by_split: dict[str, Counter] = defaultdict(Counter)
    prefix_counter: Counter = Counter()
    bad_format: list[str] = []
    bad_class_id: list[str] = []
    bad_coord: list[str] = []
    corrupt_images: list[str] = []
    zero_byte: list[str] = []
    orphan_labels: list[str] = []
    empty_labels: list[str] = []
    md5_by_split: dict[str, dict[str, str]] = {}

    for sp in SPLITS:
        img_dir = PROC_ROOT / "images" / sp
        lbl_dir = PROC_ROOT / "labels" / sp
        if not img_dir.is_dir():
            errors.append(f"缺少目录 images/{sp}")
            continue
        if not lbl_dir.is_dir():
            errors.append(f"缺少目录 labels/{sp}")
            continue

        imgs = sorted(p for p in img_dir.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS)
        lbls = sorted(p for p in lbl_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt")

        img_stems = {p.stem for p in imgs}
        lbl_stems = {p.stem for p in lbls}
        for s in sorted(lbl_stems - img_stems):
            orphan_labels.append(f"{sp}/{s}.txt (无对应图片)")

        per_split_img[sp] = len(imgs)
        per_split_lbl[sp] = len(lbls)

        md5_map: dict[str, str] = {}
        for img in imgs:
            size = img.stat().st_size
            if size == 0:
                zero_byte.append(f"{sp}/{img.name}")
                continue
            try:
                with Image.open(img) as im:
                    im.verify()
            except Exception as e:                       # noqa: BLE001
                corrupt_images.append(f"{sp}/{img.name}: {e}")

            prefix_counter[img.name.split("_")[0] + "_"] += 1
            md5_map[file_md5(img)] = img.name

        md5_by_split[sp] = md5_map

        for lbl in lbls:
            text = lbl.read_text(encoding="utf-8").strip()
            if not text:
                per_split_empty[sp] += 1
                empty_labels.append(f"{sp}/{lbl.stem}")
                continue
            for lineno, raw in enumerate(text.splitlines(), 1):
                parts = raw.split()
                if len(parts) != 5:
                    bad_format.append(f"{sp}/{lbl.name}:{lineno} 字段数={len(parts)}")
                    continue
                try:
                    cid = int(parts[0])
                    vals = [float(x) for x in parts[1:]]
                except ValueError:
                    bad_format.append(f"{sp}/{lbl.name}:{lineno} 非数值")
                    continue
                if nc is not None and not (0 <= cid < nc):
                    bad_class_id.append(f"{sp}/{lbl.name}:{lineno} id={cid}")
                    continue
                cx, cy, w, h = vals
                if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
                    bad_coord.append(f"{sp}/{lbl.name}:{lineno} 中心越界 ({cx},{cy})")
                elif not (0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                    bad_coord.append(f"{sp}/{lbl.name}:{lineno} 宽高非法 ({w},{h})")
                else:
                    per_split_obj[sp] += 1
                    class_counter[cid] += 1
                    class_by_split[cid][sp] += 1

    # ------------------------------------------------------ 3. 划分泄漏复查
    cross_leak: list[tuple[str, str, str]] = []
    seen: dict[str, tuple[str, str]] = {}
    for sp in SPLITS:
        for digest, fname in md5_by_split.get(sp, {}).items():
            if digest in seen:
                prev_sp, prev_name = seen[digest]
                cross_leak.append((prev_sp, prev_name, f"{sp}/{fname}"))
            else:
                seen[digest] = (sp, fname)

    # -------------------------------------------------------------- 4. 输出
    print("-" * 72)
    print(f"{'划分':<6}{'图片':>8}{'标签':>8}{'实例':>10}{'空标签':>8}")
    for sp in SPLITS:
        print(f"{sp:<6}{per_split_img[sp]:>8}{per_split_lbl[sp]:>8}"
              f"{per_split_obj[sp]:>10}{per_split_empty[sp]:>8}")
    tot_img = sum(per_split_img.values())
    tot_lbl = sum(per_split_lbl.values())
    tot_obj = sum(per_split_obj.values())
    print(f"{'合计':<6}{tot_img:>8}{tot_lbl:>8}{tot_obj:>10}"
          f"{sum(per_split_empty.values()):>8}")
    print("-" * 72)

    # 判定
    if per_split_img != per_split_lbl:
        for sp in SPLITS:
            if per_split_img[sp] != per_split_lbl[sp]:
                errors.append(
                    f"{sp}: 图片 {per_split_img[sp]} != 标签 {per_split_lbl[sp]}"
                )
    if orphan_labels:
        errors.append(f"孤立标签 {len(orphan_labels)} 个: {orphan_labels[:3]}")
    if corrupt_images:
        errors.append(f"损坏图片 {len(corrupt_images)} 个: {corrupt_images[:3]}")
    if zero_byte:
        errors.append(f"零字节图片 {len(zero_byte)} 个: {zero_byte[:3]}")
    if bad_format:
        errors.append(f"格式错误标注行 {len(bad_format)} 条: {bad_format[:3]}")
    if bad_class_id:
        errors.append(f"类 ID 越界 {len(bad_class_id)} 条: {bad_class_id[:3]}")
    if bad_coord:
        errors.append(f"坐标非法 {len(bad_coord)} 条: {bad_coord[:3]}")
    if cross_leak:
        errors.append(f"跨划分重复 {len(cross_leak)} 组: {cross_leak[:3]}")
    if nc is not None and nc != len(names or []):
        errors.append(f"data.yaml: nc({nc}) != len(names)({len(names)})")
    if names and max(class_counter, default=-1) >= len(names):
        errors.append("存在超出 names 范围的 class id")

    print(f"损坏图片     : {len(corrupt_images)}")
    print(f"零字节图片   : {len(zero_byte)}")
    print(f"孤立标签     : {len(orphan_labels)}")
    print(f"格式错误行   : {len(bad_format)}")
    print(f"类 ID 越界   : {len(bad_class_id)}")
    print(f"坐标非法行   : {len(bad_coord)}")
    print(f"跨划分重复   : {len(cross_leak)}   <-- 必须为 0")
    print(f"空标签       : {len(empty_labels)} (背景负样本, 合法)")
    print(f"来源前缀分布 : {dict(prefix_counter)}")
    print("-" * 72)

    if names:
        print(f"{'ID':<4}{'类名':<18}{'实例':>8}   train/val/test")
        for cid in sorted(class_counter):
            nm = names[cid] if cid < len(names) else f"<越界:{cid}>"
            c = class_by_split[cid]
            print(f"{cid:<4}{nm:<18}{class_counter[cid]:>8}   "
                  f"{c['train']}/{c['val']}/{c['test']}")
        missing = [n for n in names if names.index(n) not in class_counter]
        if missing:
            warnings.append(f"以下类在转换后无任何实例: {missing}")

    print("-" * 72)
    for w in warnings:
        print(f"[WARN ] {w}")
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        print(f"\n[FAILED] 共 {len(errors)} 项未通过。")
        return 1
    print(f"\n[PASSED] 全部检查通过 — {tot_img} 图 / {tot_obj} 实例 / "
          f"{len(names) if names else '?'} 类")

    # 写报告
    report = {
        "passed": True,
        "total_images": tot_img,
        "total_labels": tot_lbl,
        "total_objects": tot_obj,
        "per_split_images": dict(per_split_img),
        "per_split_objects": dict(per_split_obj),
        "per_split_empty": dict(per_split_empty),
        "class_instances": {names[c]: class_counter[c] for c in sorted(class_counter)} if names else {},
        "empty_labels": empty_labels,
        "prefix_distribution": dict(prefix_counter),
        "cross_split_duplicates": len(cross_leak),
        "warnings": warnings,
    }
    out = PROJECT_ROOT / "docs" / "phase11_check_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 自检报告: {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
