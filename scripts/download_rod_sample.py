# -*- coding: utf-8 -*-
"""
Phase 09 — 安全下载 ROD-Dataset 采样子集 (requests 直写 + 多线程断点续传)
只下载 Phase 08 已确认的数据集: Abtinz/Obstacle-Detection-Dataset-YOLO (CC BY 4.0, 原生 YOLO)
- requests 直写, 避免 huggingface_hub 的 .lock 清理触发沙箱 safe-delete 守卫。
- ThreadPoolExecutor 并发下载 (W=16), 大幅缩短耗时, 以便在本轮内完成。
- 断点续传: 已存在且 >=100 字节的文件跳过。
- 每 500 张写一次检查点 (download_manifest.json)。
- 目标: ~4000 张图 (test 全量 1629 + valid 采样 1371 + train 采样 1000) + 配对标签。
- 不转换、不训练。
- 传输通道说明: 2026-09-01 实测本沙箱环境 curl/schannel 报 SEC_E_NO_CREDENTIALS
  (TLS 凭证不可用), 而 Python requests 可正常访问 HF (HTTP 200); 故下载改用 requests 直写。
"""
import os
import sys
import json
import random
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\BlindRoadMonitor\scripts")
from disk_manager import get_disk_info, check_before_operation, GB

REPO = "Abtinz/Obstacle-Detection-Dataset-YOLO"
REPO_TYPE = "dataset"
REVISION = "main"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/"
RAW = r"D:\BlindRoadMonitor\datasets\raw\rod_dataset"
SEED = 20260831
N_TRAIN = 1000
N_VALID = 1371
KEEP_TEST_FULL = True
MIN_BYTES = 100          # 图片最小字节阈值 (图片远大于此)
MIN_BYTES_LBL = 0        # 标签最小字节阈值: 标签仅几十字节, 0 字节空标签也是合法文件
WORKERS = 5              # 并发线程数 (HF 对高并发限流 429, 实测 16 触发; 5 为安全值)
TIMEOUT = 120
MAX_RETRIES = 5          # 429/5xx 指数退避重试次数


def run_curl(url, out_path, timeout=TIMEOUT, min_bytes=MIN_BYTES):
    """下载单个文件到 out_path (requests 直写, 失败/过小返回 False)。
    对 429 (限流) / 5xx 做指数退避重试; 其余错误直接返回 False。"""
    out_path = out_path.replace("/", "\\")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    delay = 2.0
    for attempt in range(MAX_RETRIES + 1):
        try:
            with requests.get(url, timeout=timeout, stream=True) as r:
                if r.status_code == 429 or r.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return False
                if r.status_code != 200:
                    return False
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if chunk:
                            f.write(chunk)
                return os.path.exists(out_path) and os.path.getsize(out_path) >= min_bytes
        except Exception:
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            return False
    return False


def already_ok(out_path, min_bytes=MIN_BYTES):
    return os.path.exists(out_path) and os.path.getsize(out_path) >= min_bytes


def save_checkpoint(manifest):
    with open(os.path.join(RAW, "download_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def main():
    os.makedirs(RAW, exist_ok=True)
    print("[1] 磁盘闸门 (disk gate)")
    info = get_disk_info("D:\\")
    print(f"    D: 当前剩余 = {info.free_gb:.2f} GB (status={info.status})")
    gate = check_before_operation("download_dataset_rod_sample", required_gb=6.0)
    print(f"    [GATE] ok={gate.ok} status={gate.status} free={gate.free_gb:.2f}GB")

    print("[2] 列举仓库文件结构 (只读 API)")
    from huggingface_hub import list_repo_files
    files = list(list_repo_files(REPO, repo_type=REPO_TYPE))
    img_paths = [f for f in files if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp"))]
    print(f"    仓库总图片: {len(img_paths)}")

    def split_of(p):
        return p.split("/")[0]

    groups = {"train": [], "valid": [], "test": []}
    for p in img_paths:
        s = split_of(p)
        if s in groups:
            groups[s].append(p)

    random.seed(SEED)
    plan = []
    for s in ["train", "valid", "test"]:
        lst = groups[s]
        if s == "test" and KEEP_TEST_FULL:
            chosen = lst
        else:
            n = {"train": N_TRAIN, "valid": N_VALID}[s]
            n = min(n, len(lst))
            chosen = random.sample(lst, n)
        plan.extend(chosen)
    print(f"[3] 采样计划: {len(plan)} 张图 (train {min(N_TRAIN,len(groups['train']))}, "
          f"valid {min(N_VALID,len(groups['valid']))}, test {len(groups['test']) if KEEP_TEST_FULL else 0})")
    print(f"    [RESUME] W={WORKERS} 并发, 已存在文件跳过")

    counts = {"images": 0, "labels": 0, "failed": 0, "skipped": 0}
    manifest = {"repo": REPO, "license": "CC BY 4.0", "seed": SEED, "splits": {}, "downloaded": []}
    split_counts = {"train": 0, "valid": 0, "test": 0}
    failed_list = []
    lock = __import__("threading").Lock()

    def worker(img_p):
        s = split_of(img_p)
        base = os.path.basename(img_p)
        img_out = os.path.join(RAW, s, "images", base)
        lbl_p = img_p.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
        lbl_out = os.path.join(RAW, s, "labels", base.rsplit(".", 1)[0] + ".txt")
        if already_ok(img_out) and already_ok(lbl_out, min_bytes=MIN_BYTES_LBL):
            return (s, True, True, True)  # split, skipped, ok_img, ok_lbl
        ok_img = run_curl(BASE + img_p, img_out, min_bytes=MIN_BYTES)
        ok_lbl = run_curl(BASE + lbl_p, lbl_out, min_bytes=MIN_BYTES_LBL)
        return (s, False, ok_img, ok_lbl)

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(worker, p): p for p in plan}
        for fut in as_completed(futs):
            s, skipped, ok_img, ok_lbl = fut.result()
            with lock:
                done += 1
                if skipped:
                    counts["skipped"] += 1
                    counts["images"] += 1
                    split_counts[s] += 1
                else:
                    if ok_img:
                        counts["images"] += 1
                        split_counts[s] += 1
                    if ok_lbl:
                        counts["labels"] += 1
                    if ok_img and ok_lbl:
                        manifest["downloaded"].append({"split": s, "image": futs[fut], "label": futs[fut].replace("/images/", "/labels/").rsplit(".",1)[0]+".txt"})
                    else:
                        counts["failed"] += 1
                        failed_list.append(futs[fut])
                if done % 500 == 0:
                    manifest["splits"] = split_counts
                    manifest["totals"] = counts
                    save_checkpoint(manifest)
                    print(f"    进度 {done}/{len(plan)} 图={counts['images']} 标签={counts['labels']} "
                          f"失败={counts['failed']} 跳过={counts['skipped']}", flush=True)

    manifest["splits"] = split_counts
    manifest["totals"] = counts
    manifest["failed"] = failed_list[:50]
    save_checkpoint(manifest)

    for extra in ["data.yaml", "README.md", "README", "classes.txt"]:
        if run_curl(BASE + extra, os.path.join(RAW, extra)):
            print(f"    已下载附加上下文文件: {extra}")

    print(f"[5] 完成 -> 图片 {counts['images']}, 标签 {counts['labels']}, "
          f"失败 {counts['failed']}, 跳过(已存在) {counts['skipped']}")
    if counts["failed"]:
        print(f"    [WARN] 失败样本示例: {failed_list[:5]}")
    def dsz(p):
        t = 0
        for r, d, fl in os.walk(p):
            for x in fl:
                t += os.path.getsize(os.path.join(r, x))
        return t
    occ = dsz(RAW) / GB
    post = info.free_gb - occ
    print(f"    数据集占用 ~ {occ:.3f} GB; 完成后 D 剩余 ~ {post:.2f} GB")


if __name__ == "__main__":
    main()
