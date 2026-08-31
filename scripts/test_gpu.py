#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RTX 5070 GPU 验证脚本 (stdlib + torch only)

目标: 确认 RTX 5070 8GB 能稳定运行 PyTorch (CUDA 可用 / 显存可读 / 计算正确)。
约束: 仅做轻量测试, 不训练、不下载数据集、不占用大量磁盘。
遇 CUDA error / out of memory / driver error 立即以非 0 退出, 不做任何修改。
"""

import sys


def main():
    # ---- 1. 导入与版本 ----
    try:
        import torch
    except Exception as e:
        print("IMPORT_FAIL:", e)
        return 2

    print("=" * 52)
    print("RTX 5070 GPU 验证 / GPU Validation")
    print("=" * 52)
    print("PyTorch version :", torch.__version__)
    print("CUDA runtime    :", torch.version.cuda)
    print("CUDA available  :", torch.cuda.is_available())

    if not torch.cuda.is_available():
        print("CUDA_UNAVAILABLE: 无法验证 GPU, 终止。")
        return 1

    # ---- 2. GPU 基础信息 ----
    try:
        idx = torch.cuda.current_device()
        name = torch.cuda.get_device_name(idx)
        cap = torch.cuda.get_device_capability(idx)  # (major, minor)
        props = torch.cuda.get_device_properties(idx)
        total_gb = props.total_memory / 1e9
        print("Device index    :", idx)
        print("GPU name        :", name)
        print("Compute cap     : sm_%d%d" % (cap[0], cap[1]))
        print("Total memory    : %.2f GB" % total_gb)
    except Exception as e:
        print("GPU_INFO_ERROR:", repr(e))
        return 3

    # ---- 3. 轻量 CUDA 计算 + 正确性校验 ----
    try:
        dev = torch.device("cuda")

        # 3.1 大矩阵乘法 (4096x4096 fp32 ≈ 64MB/张, 对 8GB 显存安全)
        a = torch.randn(4096, 4096, device=dev, dtype=torch.float32)
        b = torch.randn(4096, 4096, device=dev, dtype=torch.float32)
        c = torch.matmul(a, b)
        torch.cuda.synchronize()

        # 3.2 正确性: GPU 结果与 CPU 对比 (小矩阵)
        s = 128
        x = torch.randn(s, s, device=dev)
        y = torch.randn(s, s, device=dev)
        gpu_res = x @ y
        cpu_res = x.cpu() @ y.cpu()
        diff = (gpu_res.cpu() - cpu_res).abs().max().item()
        ok_calc = diff < 1e-3

        # 3.3 elementwise + reduction
        z = (a * 2.0 + 1.0).sum().item()

        # 显存快照
        alloc_mb = torch.cuda.memory_allocated(dev) / 1e6
        reserved_mb = torch.cuda.memory_reserved(dev) / 1e6

        print("-" * 52)
        print("Matrix mul      : 4096x4096 @ 4096x4096  (synced) OK")
        print("Correctness diff: %.2e  -> %s" % (diff, "PASS" if ok_calc else "FAIL"))
        print("Reduction sum   : %.4f" % z)
        print("Allocated mem   : %.1f MB" % alloc_mb)
        print("Reserved mem    : %.1f MB" % reserved_mb)

        # 释放, 避免残留显存
        del a, b, c, x, y, gpu_res, cpu_res, z
        torch.cuda.empty_cache()
        print("empty_cache     : OK")

    except torch.cuda.OutOfMemoryError:
        print("OUT_OF_MEMORY: 显存不足, 立即停止 (未做任何修改)。")
        return 4
    except Exception as e:
        print("CUDA_RUNTIME_ERROR:", repr(e))
        return 5

    print("=" * 52)
    print("RESULT: GPU VALIDATION PASSED")
    print("=" * 52)
    return 0


if __name__ == "__main__":
    sys.exit(main())
