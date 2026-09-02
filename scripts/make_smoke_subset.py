# -*- coding: utf-8 -*-
"""Phase 13 — 创建 smoke test 子集 (从 processed 复制, 不动原始数据)
- train: 450 张 (含 blind_road 优先 ≥ 40), val: 100 张 (含 blind_road ≥ 10)
- 输出: datasets/smoke_test/{images,labels}/{train,val}
"""
import os
import random
import shutil

PROC = r"D:\BlindRoadMonitor\datasets\processed"
SMOKE = r"D:\BlindRoadMonitor\datasets\smoke_test"
SEED = 20260902
N_TRAIN = 450
N_VAL = 100
MIN_BLIND_TRAIN = 40
MIN_BLIND_VAL = 10

random.seed(SEED)


def pick(split_src, n, min_blind):
    img_dir = os.path.join(PROC, "images", split_src)
    lbl_dir = os.path.join(PROC, "labels", split_src)
    stems = [f[:-4] for f in os.listdir(img_dir) if f.endswith(".jpg")]
    blind = []
    other = []
    for s in stems:
        lp = os.path.join(lbl_dir, s + ".txt")
        try:
            with open(lp, encoding="utf-8") as f:
                first = f.readline().strip()
            has_blind = first.split()[0] == "0" if first else False
        except Exception:
            has_blind = False
        (blind if has_blind else other).append(s)
    random.shuffle(other)
    b = blind[:min_blind]
    rest = other[: max(0, n - len(b))]
    chosen = b + rest
    random.shuffle(chosen)
    return chosen, len(blind)


def copy_set(src_split, dst_split, stems):
    simg = os.path.join(PROC, "images", src_split)
    slbl = os.path.join(PROC, "labels", src_split)
    dimg = os.path.join(SMOKE, "images", dst_split)
    dlbl = os.path.join(SMOKE, "labels", dst_split)
    os.makedirs(dimg, exist_ok=True)
    os.makedirs(dlbl, exist_ok=True)
    for s in stems:
        shutil.copy2(os.path.join(simg, s + ".jpg"), os.path.join(dimg, s + ".jpg"))
        shutil.copy2(os.path.join(slbl, s + ".txt"), os.path.join(dlbl, s + ".txt"))


def main():
    train_stems, tb = pick("train", N_TRAIN, MIN_BLIND_TRAIN)
    val_stems, vb = pick("val", N_VAL, MIN_BLIND_VAL)
    copy_set("train", "train", train_stems)
    copy_set("val", "val", val_stems)
    print(f"train: {len(train_stems)} 张 (含盲道 {sum(1 for s in train_stems if True)}; 盲道源共 {tb})")
    # 精确统计盲道数
    def count_blind(dst):
        n = 0
        for f in os.listdir(os.path.join(SMOKE, "labels", dst)):
            with open(os.path.join(SMOKE, "labels", dst, f), encoding="utf-8") as fh:
                if any(l.split()[0] == "0" for l in fh if l.strip()):
                    n += 1
        return n
    print(f"实际含盲道标签: train={count_blind('train')} val={count_blind('val')}")
    print(f"val: {len(val_stems)} 张")
    # 写 yaml
    names = ["blind_road", "person", "pole", "car", "tree", "motorcycle",
             "warning_column", "crosswalk", "bicycle", "green_light", "red_light",
             "roadblock", "cone", "truck", "sign", "trash_bin", "bus", "tricycle",
             "fire_hydrant", "dog", "stairs", "manhole", "guard_rail", "chair",
             "bench", "plant_pot"]
    yaml_path = os.path.join(SMOKE, "data.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(f"path: {SMOKE.replace(os.sep, '/')}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write(f"nc: {len(names)}\n")
        f.write("names: [" + ", ".join(f"'{n}'" for n in names) + "]\n")
    print(f"yaml: {yaml_path}")


if __name__ == "__main__":
    main()
