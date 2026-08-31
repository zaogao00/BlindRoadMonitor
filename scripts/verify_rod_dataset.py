# -*- coding: utf-8 -*-
"""
Phase 09 — 校验已下载 ROD-Dataset 子集完整性
检查: 文件数量 / 图片数量 / 标签数量 / 文件完整性 (0字节, 图片可打开, 标签非空)
"""
import os
import json
from collections import Counter

RAW = r"D:\BlindRoadMonitor\datasets\raw\rod_dataset"
IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def main():
    print(f"[VERIFY] {RAW}")
    assert os.path.isdir(RAW), "数据集目录不存在, 下载可能未完成"

    report = {"splits": {}, "totals": {}, "issues": []}
    total_img = total_lbl = 0
    # dynamic import PIL only if available (optional integrity check)
    try:
        from PIL import Image
        has_pil = True
    except Exception:
        has_pil = False
    print(f"    PIL 可用: {has_pil}")

    for split in ["train", "valid", "test"]:
        idir = os.path.join(RAW, split, "images")
        ldir = os.path.join(RAW, split, "labels")
        if not os.path.isdir(idir):
            report["splits"][split] = {"images": 0, "labels": 0}
            continue
        imgs = sorted([f for f in os.listdir(idir) if f.lower().endswith(IMG_EXT)])
        labels = sorted([f for f in os.listdir(ldir) if f.lower().endswith(".txt")]) if os.path.isdir(ldir) else []
        # 配对检查
        img_stems = {os.path.splitext(f)[0] for f in imgs}
        lbl_stems = {os.path.splitext(f)[0] for f in labels}
        missing_lbl = img_stems - lbl_stems
        missing_img = lbl_stems - img_stems
        # 完整性: 0字节 / 损坏
        zero_byte = []
        corrupt = []
        for f in imgs:
            fp = os.path.join(idir, f)
            if os.path.getsize(fp) == 0:
                zero_byte.append(f)
            elif has_pil:
                try:
                    with Image.open(fp) as im:
                        im.verify()
                except Exception:
                    corrupt.append(f)
        empty_lbl = []
        for f in labels:
            fp = os.path.join(ldir, f)
            if os.path.getsize(fp) == 0:
                empty_lbl.append(f)
        report["splits"][split] = {
            "images": len(imgs),
            "labels": len(labels),
            "missing_label": sorted(missing_lbl)[:10],
            "missing_image": sorted(missing_img)[:10],
            "zero_byte_images": zero_byte,
            "corrupt_images": corrupt[:10],
            "empty_labels": empty_lbl[:10],
        }
        total_img += len(imgs)
        total_lbl += len(labels)
        # 汇总问题
        if missing_lbl:
            report["issues"].append(f"{split}: {len(missing_lbl)} 张图缺标签")
        if missing_img:
            report["issues"].append(f"{split}: {len(missing_img)} 个标签缺图")
        if zero_byte:
            report["issues"].append(f"{split}: {len(zero_byte)} 个 0 字节图片")
        if corrupt:
            report["issues"].append(f"{split}: {len(corrupt)} 个损坏图片")
        if empty_lbl:
            report["issues"].append(f"{split}: {len(empty_lbl)} 个空标签")

    report["totals"] = {"images": total_img, "labels": total_lbl}

    # 占用空间
    def dsz(p):
        t = 0
        for r, d, fl in os.walk(p):
            for x in fl:
                t += os.path.getsize(os.path.join(r, x))
        return t
    occ = dsz(RAW)
    report["occupancy_bytes"] = occ
    print(f"    图片总计: {total_img}")
    print(f"    标签总计: {total_lbl}")
    print(f"    占用空间: {occ/1024/1024:.1f} MB")
    for s in ["train", "valid", "test"]:
        d = report["splits"].get(s, {})
        print(f"    {s}: img={d.get('images',0)} lbl={d.get('labels',0)} "
              f"missing_lbl={len(d.get('missing_label',[]))} missing_img={len(d.get('missing_image',[]))} "
              f"zero={len(d.get('zero_byte_images',[]))} corrupt={len(d.get('corrupt_images',[]))} empty_lbl={len(d.get('empty_labels',[]))}")
    print(f"    问题汇总: {report['issues'] if report['issues'] else '无'}")

    with open(os.path.join(RAW, "verify_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("[VERIFY] 已写 verify_report.json")
    return report


if __name__ == "__main__":
    main()
