#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/check_yolo.py — YOLO / PyTorch / CUDA / GPU 一体化环境校验

用途:
    确认当前 Python 来自本项目隔离 venv, 并且
    Python / PyTorch / CUDA / Ultralytics / GPU 全部正常工作。

设计原则 (与项目约束一致):
    - 仅做轻量校验 (小矩阵计算), 不训练、不下载、不占大磁盘、不长时间运行。
    - 任何异常 (import 失败 / CUDA error / OOM / driver error) 立即捕获并打印,
      以非零退出码结束, 不擅自修改 CUDA 或卸载驱动。

退出码:
    0 = 全部正常
    1 = 任一检查失败
"""

import os
import sys

# 期望的 venv 解释器根路径 (本项目隔离环境)
EXPECTED_VENV = os.path.normcase(r"D:\BlindRoadMonitor.venv")


def _section(title: str) -> None:
    print("\n" + "=" * 56)
    print(title)
    print("=" * 56)


def check_python_venv() -> bool:
    _section("1. Python / venv 校验")
    exe = sys.executable
    print(f"  解释器 : {exe}")
    print(f"  版本   : {sys.version.replace(chr(10), ' ')}")
    norm = os.path.normcase(os.path.dirname(os.path.dirname(exe)))
    ok = norm == EXPECTED_VENV or norm.startswith(EXPECTED_VENV)
    if ok:
        print("  [PASS] 当前 Python 来自隔离 venv: D:\\BlindRoadMonitor.venv")
    else:
        print(f"  [FAIL] 当前 Python 不在预期 venv 中 (期望前缀: {EXPECTED_VENV})")
    return ok


def check_ultralytics() -> str:
    _section("2. Ultralytics (YOLO) 校验")
    try:
        import ultralytics
        ver = getattr(ultralytics, "__version__", "unknown")
        print(f"  [PASS] ultralytics 导入成功, 版本 = {ver}")
        return ver
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 无法导入 ultralytics: {e!r}")
        raise


def check_pytorch_cuda() -> bool:
    _section("3. PyTorch / CUDA 校验")
    try:
        import torch
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 无法导入 torch: {e!r}")
        raise

    print(f"  PyTorch 版本 : {torch.__version__}")
    cuda_available = torch.cuda.is_available()
    print(f"  CUDA 可用    : {cuda_available}")
    if not cuda_available:
        print("  [FAIL] torch.cuda.is_available() == False")
        return False

    try:
        dev = torch.cuda.current_device()
        name = torch.cuda.get_device_name(dev)
        cap = torch.cuda.get_device_capability(dev)  # (major, minor)
        props = torch.cuda.get_device_properties(dev)
        total_mb = props.total_memory / (1024 ** 2)
        print(f"  GPU 设备     : cuda:{dev} — {name}")
        print(f"  计算能力     : sm_{cap[0]}{cap[1]}")
        print(f"  显存总量     : {total_mb:.0f} MiB ({total_mb / 1024:.2f} GB)")
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 读取 GPU 属性失败 (driver/CUDA error?): {e!r}")
        raise
    print("  [PASS] PyTorch + CUDA 正常")
    return True


def check_gpu_compute() -> bool:
    _section("4. GPU 计算校验 (轻量矩阵乘法)")
    import torch

    try:
        n = 2048
        a = torch.randn(n, n, device="cuda")
        b = torch.randn(n, n, device="cuda")
        c = torch.matmul(a, b)
        # 触发计算并取一个数, 确保真实执行
        _ = c[0, 0].item()
        print(f"  [PASS] 在 GPU 上完成 {n}x{n} 矩阵乘法, 结果有效")
        # 释放显存
        del a, b, c
        torch.cuda.empty_cache()
        return True
    except torch.cuda.OutOfMemoryError:  # noqa: BLE001
        print("  [FAIL] 显存不足 (Out of Memory)")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] GPU 计算异常 (CUDA error / driver error?): {e!r}")
        return False


def main() -> int:
    _section("YOLO 环境一体化校验 (scripts/check_yolo.py)")
    print(f"  工作目录 : {os.getcwd()}")

    results = {}
    try:
        results["python_venv"] = check_python_venv()
        ultralytics_ver = check_ultralytics()
        results["pytorch_cuda"] = check_pytorch_cuda()
        results["gpu_compute"] = check_gpu_compute()
    except Exception as e:  # noqa: BLE001
        print(f"\n[FATAL] 校验过程中抛出异常: {e!r}")
        return 1

    _section("汇总")
    for k, v in results.items():
        print(f"  {k:16s}: {'PASS' if v else 'FAIL'}")

    all_ok = all(results.values())
    print(
        "\n[RESULT] "
        + ("✅ 全部正常 — YOLO / PyTorch / CUDA / GPU 就绪" if all_ok else "❌ 存在失败项, 请检查上方输出")
    )
    print(f"[INFO] ultralytics 版本 = {ultralytics_ver}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
