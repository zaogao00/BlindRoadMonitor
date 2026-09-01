# -*- coding: utf-8 -*-
"""
Phase 09 补充 — 安全下载 WOTR 数据集 (Google Drive, 4.0 GB, MIT)
WOTR: A Dataset for the Visually Impaired Walk On The Road (Displays 2023, MIT)
- 唯一同时含「盲道类(tactile_paving/blind_road) + 15 类障碍物」且 MIT 授权的数据集
- 来源: https://github.com/kxzr/WOTR (README 内 Google Drive share link, 公开可下载, 零凭证)
- 实现: gdown 流程 (病毒扫描确认页 -> usercontent GET), Range 断点续传
- 不转换、不训练。
"""
import os
import re
import sys
import time
import requests

sys.path.insert(0, r"D:\BlindRoadMonitor\scripts")
from disk_manager import get_disk_info, check_before_operation

FILE_ID = "11Idy50HhzedOXxpxYuoecfqMNHGcxVfj"
EXPECTED_SIZE = 4244840539  # Drive 实测 content-length
RAW = r"D:\BlindRoadMonitor\datasets\raw\wotr"
ZIP_PATH = os.path.join(RAW, "WOTR.zip")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def main():
    os.makedirs(RAW, exist_ok=True)

    print("[1] 磁盘闸门 (disk gate)")
    info = get_disk_info("D:\\")
    print(f"    D: 当前剩余 = {info.free_gb:.2f} GB (status={info.status})")
    gate = check_before_operation("download_dataset_wotr", required_gb=12.0)
    print(f"    [GATE] ok={gate.ok} status={gate.status} free={gate.free_gb:.2f}GB")
    if not gate.ok:
        print("    [ABORT] 磁盘闸门未通过, 停止下载。")
        return 1

    s = requests.Session()
    s.headers.update({"User-Agent": UA})

    print("[2] 获取下载 token (病毒扫描确认页)")
    u1 = f"https://drive.google.com/uc?export=download&id={FILE_ID}"
    r1 = s.get(u1, timeout=60, allow_redirects=True)
    m = re.search(r'name="uuid"[^>]*value="([^"]+)"', r1.text)
    uuid = m.group(1) if m else ""
    print(f"    uuid: {uuid}")

    dl_url = f"https://drive.usercontent.google.com/download?id={FILE_ID}&export=download&confirm=t&uuid={uuid}"

    # 断点续传: 检查本地已有大小
    existing = os.path.getsize(ZIP_PATH) if os.path.exists(ZIP_PATH) else 0
    if existing >= EXPECTED_SIZE:
        print(f"[3] 已存在完整 WOTR.zip ({existing / 1024**3:.2f} GiB), 跳过下载。")
        return 0
    print(f"[3] 断点续传: 已有 {existing / 1024**3:.3f} GiB, 需下载 {(EXPECTED_SIZE - existing) / 1024**3:.2f} GiB")

    headers = {"User-Agent": UA}
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"
    start = time.time()
    with requests.get(dl_url, timeout=120, stream=True, headers=headers) as r:
        if r.status_code not in (200, 206):
            print(f"    [ERR] HTTP {r.status_code}")
            return 1
        mode = "ab" if existing > 0 else "wb"
        done = existing
        last_report = 0.0
        with open(ZIP_PATH, mode) as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    now = time.time()
                    if now - last_report >= 15:
                        speed = done / max(now - start, 0.1) / 1024 / 1024
                        pct = done / EXPECTED_SIZE * 100
                        print(f"    进度 {done / 1024**3:.2f}/{EXPECTED_SIZE / 1024**3:.2f} GiB "
                              f"({pct:.1f}%)  {speed:.1f} MB/s", flush=True)
                        last_report = now

    actual = os.path.getsize(ZIP_PATH)
    print(f"[4] 下载完成: {actual} bytes (期望 {EXPECTED_SIZE})")
    if actual >= EXPECTED_SIZE:
        print("    [OK] 大小匹配")
    else:
        print("    [WARN] 大小不匹配, 可重跑续传")
        return 1

    # 校验 ZIP 完整性
    print("[5] 校验 ZIP 完整性 (testzip)")
    import zipfile
    try:
        with zipfile.ZipFile(ZIP_PATH) as zf:
            bad = zf.testzip()
        print(f"    [OK] ZIP 完整 (badfile={bad})")
    except Exception as e:
        print(f"    [ERR] ZIP 校验失败: {e}")
        return 1

    occ = sum(os.path.getsize(os.path.join(r_, f_)) for r_, d_, fs in os.walk(RAW) for f_ in fs)
    print(f"    占用: {occ / 1024**3:.2f} GiB; 完成后 D 剩余 ~ {info.free_gb - occ / 1024**3:.2f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
