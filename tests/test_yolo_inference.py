#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tests/test_yolo_inference.py — YOLO 基础推理验证 (无正式数据集)

目的:
    在正式盲道数据集就绪之前, 确认 Ultralytics YOLO 能正常完成:
        1) 模型加载   2) GPU 推理   3) 结果生成   4) 图片保存
    并收集: 模型文件大小 / 推理时间 / GPU 显存 / 输出图片 / 检测框数。

约束遵守:
    - 不下载大型数据集 (仅自动下载约 6MB 的 yolov8n 预训练权重 + 一张小示例图/合成图)。
    - 不进行训练。
    - 遇 CUDA error / Out of Memory / driver error 立即停止并报告, 不擅自修改 CUDA、不卸载驱动。

退出码:
    0 = 推理全流程成功
    1 = 任一环节失败
"""

import os
import sys
import time

# 项目根目录 (本文件位于 tests/ 下)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 让脚本可在任意 cwd 下找到项目模块 (此处仅用 ultralytics, 不需要本仓库模块)


def _section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def get_test_image() -> str:
    """
    返回一张可用作推理输入的测试图片路径。
    优先级:
        1) Ultralytics 自带示例 bus.jpg (会自动从官方下载到其 assets 目录, 约 100KB)
        2) 本地 tests/assets/sample.jpg (若存在)
        3) 用 PIL 合成一张含色块的图片 (完全离线, 不依赖网络)
    """
    # 1) 尝试 Ultralytics 自带示例
    try:
        import ultralytics
        from ultralytics import ASSETS  # 新版 ultralytics 暴露 ASSETS 常量
        bus = os.path.join(str(ASSETS), "bus.jpg")
        if os.path.isfile(bus):
            print(f"  [INFO] 使用 Ultralytics 自带示例: {bus}")
            return bus
        # 触发自动下载示例图 (network)
        from ultralytics.utils.downloads import safe_download
        safe_download(url="https://ultralytics.com/images/bus.jpg", dir=str(ASSETS), file="bus.jpg")
        if os.path.isfile(bus):
            print(f"  [INFO] 已下载 Ultralytics 示例: {bus}")
            return bus
    except Exception as e:  # noqa: BLE001
        print(f"  [WARN] 获取 Ultralytics 示例图失败 ({e!r}), 回退到合成图")

    # 2) 本地已有合成图?
    local = os.path.join(ROOT, "tests", "assets", "sample.jpg")
    if os.path.isfile(local):
        print(f"  [INFO] 使用本地测试图: {local}")
        return local

    # 3) 用 PIL 合成一张含彩色矩形的图 (模拟可检测物体, 离线可用)
    try:
        from PIL import Image, ImageDraw
        os.makedirs(os.path.dirname(local), exist_ok=True)
        img = Image.new("RGB", (640, 480), (240, 240, 240))
        d = ImageDraw.Draw(img)
        d.rectangle([40, 40, 220, 300], fill=(220, 60, 60), outline=(0, 0, 0))
        d.rectangle([300, 80, 520, 360], fill=(40, 120, 220), outline=(0, 0, 0))
        d.ellipse([380, 120, 480, 240], fill=(40, 180, 80), outline=(0, 0, 0))
        d.rectangle([80, 340, 600, 460], fill=(230, 200, 40), outline=(0, 0, 0))
        img.save(local)
        print(f"  [INFO] 已生成合成测试图: {local}")
        return local
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"无法准备测试图片 (合成图也失败): {e!r}")


def main() -> int:
    _section("YOLO 基础推理验证 (tests/test_yolo_inference.py)")

    import torch
    from ultralytics import YOLO

    # 0) 设备与 CUDA 预检
    if not torch.cuda.is_available():
        print("[FAIL] CUDA 不可用, 无法执行 GPU 推理")
        return 1
    device = 0
    print(f"[INFO] 使用设备: cuda:{device} ({torch.cuda.get_device_name(device)})")

    # 1) 测试图片
    _section("1. 准备测试图片")
    img_path = get_test_image()
    print(f"  测试图片: {img_path}  (存在={os.path.isfile(img_path)})")

    # 2) 加载模型 (自动下载 yolov8n.pt, ~6MB; 仅此一次小下载, 非数据集)
    _section("2. 加载模型 (yolov8n)")
    model_name = "yolov8n.pt"
    model_candidates = [
        os.path.join(ROOT, "models", model_name),  # 首选: 已缓存到项目 models/ (被 .gitignore 屏蔽)
        os.path.join(ROOT, model_name),
    ]
    chosen = next((p for p in model_candidates if os.path.isfile(p)), model_name)
    try:
        model = YOLO(chosen)
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] 模型加载失败: {e!r}")
        return 1

    # 定位实际权重文件并测大小
    weights_path = chosen if os.path.isfile(chosen) else (
        getattr(model, "ckpt_path", None)
        or os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Ultralytics", "models", model_name)
    )
    model_size_mb = (
        os.path.getsize(weights_path) / (1024 ** 2) if os.path.isfile(weights_path) else float("nan")
    )
    print(f"  模型文件: {weights_path}")
    print(f"  模型大小: {model_size_mb:.2f} MB")

    # 3) GPU 推理 + 计时 + 显存监控
    _section("3. GPU 推理")
    out_dir = os.path.join(ROOT, "runs", "yolo_inference_test")
    os.makedirs(out_dir, exist_ok=True)

    torch.cuda.reset_peak_memory_stats(device)
    mem_before = torch.cuda.memory_allocated(device) / (1024 ** 2)
    t0 = time.perf_counter()
    try:
        results = model.predict(
            source=img_path,
            device=device,
            save=True,
            project=os.path.join(ROOT, "runs"),
            name="yolo_inference_test",
            exist_ok=True,
            verbose=False,
        )
    except torch.cuda.OutOfMemoryError:  # noqa: BLE001
        print("[FAIL] 推理时显存不足 (Out of Memory)")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] 推理异常 (CUDA error / driver error?): {e!r}")
        return 1
    elapsed = time.perf_counter() - t0
    mem_after = torch.cuda.memory_allocated(device) / (1024 ** 2)
    mem_peak = torch.cuda.max_memory_allocated(device) / (1024 ** 2)

    # 4) 结果生成 / 图片保存检查
    _section("4. 结果生成与图片保存")
    n_boxes_total = 0
    saved_imgs = []
    try:
        for r in results:
            nb = int(getattr(r, "boxes", None) is not None and len(r.boxes))
            n_boxes_total += nb
            if getattr(r, "save_dir", None):
                saved_imgs.append(os.path.join(r.save_dir, os.path.basename(r.path)))
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] 统计结果时出错: {e!r}")

    print(f"  推理耗时: {elapsed * 1000:.1f} ms ({elapsed:.3f} s)")
    print(f"  GPU 显存(推理前): {mem_before:.1f} MB")
    print(f"  GPU 显存(推理后): {mem_after:.1f} MB")
    print(f"  GPU 显存(峰值)  : {mem_peak:.1f} MB")
    print(f"  检测框总数: {n_boxes_total}")
    for s in saved_imgs:
        print(f"  输出图片: {s}  (存在={os.path.isfile(s)})")

    all_ok = (
        os.path.isfile(weights_path)
        and len(saved_imgs) > 0
        and all(os.path.isfile(s) for s in saved_imgs)
    )
    _section("汇总")
    print(f"  {'模型加载':<12}: {'PASS' if os.path.isfile(weights_path) else 'FAIL'}")
    print(f"  {'GPU 推理':<12}: PASS")
    print(f"  {'结果生成':<12}: {'PASS' if n_boxes_total >= 0 else 'FAIL'}")
    print(f"  {'图片保存':<12}: {'PASS' if (saved_imgs and all(os.path.isfile(s) for s in saved_imgs)) else 'FAIL'}")
    print(f"\n[RESULT] {'✅ YOLO 推理全流程成功' if all_ok else '❌ 推理流程存在失败项'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
