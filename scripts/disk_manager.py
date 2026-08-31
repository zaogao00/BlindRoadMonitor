#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
disk_manager.py — 项目磁盘安全管理模块 (stdlib only, 无第三方依赖)

职责:
  1. 获取指定磁盘的剩余空间 / 已用空间 / 总空间。
  2. 计算任意目录所占用的磁盘空间。
  3. 在“大型操作”(下载数据集 / 解压 / 训练 / 安装) 之前做空间检查,
     依据阈值返回 NORMAL / WARNING / DANGER 状态, 并给出是否允许继续的判断。

设计原则 (来自项目磁盘安全规范):
  - D 盘剩余 >= 30GB  -> NORMAL   允许正常工作
  - D 盘剩余 15~30GB  -> WARNING  禁止扩大数据规模 / 下载大型数据集 / 自动删除
  - D 盘剩余 < 15GB   -> DANGER   立即停止大型操作, 等待用户指令

该模块不执行任何写操作 / 删除操作, 仅做“只读探测 + 决策建议”。
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# 磁盘阈值配置 (单位: 字节)
# ---------------------------------------------------------------------------
GB = 1024 ** 3

THRESHOLD_NORMAL = 30 * GB   # >= 30GB => NORMAL
THRESHOLD_WARNING = 15 * GB  # >= 15GB 且 < 30GB => WARNING; < 15GB => DANGER

# 默认监控盘符 (本项目硬件在 D 盘)
DEFAULT_DRIVE = "D:\\"


# ---------------------------------------------------------------------------
# 状态常量
# ---------------------------------------------------------------------------
class DiskStatus:
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    DANGER = "DANGER"


# 每个状态对应的可执行 / 禁止行为说明
STATUS_POLICY = {
    DiskStatus.NORMAL: "允许正常工作。",
    DiskStatus.WARNING: "禁止扩大数据规模；禁止下载新的大型数据集；禁止自动删除文件。",
    DiskStatus.DANGER: "立即停止大型操作。不要下载 / 解压 / 训练 / 删除任何用户数据。等待用户指令。",
}


@dataclass
class DiskInfo:
    drive: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    status: str = ""
    policy: str = ""

    @property
    def total_gb(self) -> float:
        return self.total_bytes / GB

    @property
    def used_gb(self) -> float:
        return self.used_bytes / GB

    @property
    def free_gb(self) -> float:
        return self.free_bytes / GB


@dataclass
class OpCheckResult:
    ok: bool
    status: str
    free_gb: float
    reason: str
    policy: str = ""


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------
def get_disk_info(drive: str = DEFAULT_DRIVE) -> DiskInfo:
    """获取指定盘符的磁盘使用情况。

    Args:
        drive: 盘符路径, 例如 "D:\\" 或 "D:"。

    Returns:
        DiskInfo 实例。
    """
    # 归一化盘符, 确保以反斜杠结尾 (shutil.disk_usage 需要有效路径)
    if len(drive) == 2 and drive[1] == ":":
        drive = drive + "\\"
    usage = shutil.disk_usage(drive)
    free = usage.free
    if free >= THRESHOLD_NORMAL:
        status = DiskStatus.NORMAL
    elif free >= THRESHOLD_WARNING:
        status = DiskStatus.WARNING
    else:
        status = DiskStatus.DANGER
    return DiskInfo(
        drive=drive,
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
        status=status,
        policy=STATUS_POLICY[status],
    )


def get_dir_size(path: str) -> int:
    """递归计算目录占用的磁盘空间 (字节)。

    对符号链接目录不递归进入, 避免重复计数。
    空目录或不存在的路径返回 0。
    """
    if not os.path.exists(path):
        return 0
    if os.path.islink(path) and os.path.isdir(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for name in files:
            fp = os.path.join(root, name)
            try:
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
            except OSError:
                continue
    return total


def format_size(num_bytes: int) -> str:
    """把字节数格式化成人类可读字符串。"""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024.0


def check_before_operation(
    op_name: str = "unknown",
    drive: str = DEFAULT_DRIVE,
    required_gb: float = 0.0,
) -> OpCheckResult:
    """在大型操作前调用, 做空间检查并返回是否允许继续。

    Args:
        op_name: 操作名称 (仅用于日志/提示)。包含 download/dataset/extract/
                 unzip/train/install/模型/数据集/下载/解压/训练/安装 等关键字时,
                 在 WARNING 状态下会被禁止。
        drive: 监控的盘符。
        required_gb: 该操作预计需要的额外空间 (GB)。默认 0。
    Returns:
        OpCheckResult
    """
    info = get_disk_info(drive)
    free_gb = info.free_gb

    # 1) 绝对安全红线: DANGER 一律禁止大型操作
    if info.status == DiskStatus.DANGER:
        return OpCheckResult(
            ok=False,
            status=info.status,
            free_gb=free_gb,
            reason=(
                f"磁盘进入 DANGER 状态 (剩余 {free_gb:.1f}GB < 15GB)。"
                f"操作 [{op_name}] 被强制中止, 等待用户指令。"
            ),
            policy=info.policy,
        )

    # 2) 空间不足预估: 预计需要空间超过剩余空间
    if required_gb > 0 and (required_gb * GB) > info.free_bytes:
        return OpCheckResult(
            ok=False,
            status=info.status,
            free_gb=free_gb,
            reason=(
                f"预估操作 [{op_name}] 需要 {required_gb:.1f}GB, "
                f"但剩余仅 {free_gb:.1f}GB, 空间不足。"
            ),
            policy=info.policy,
        )

    # 3) WARNING 状态: 禁止“扩大数据规模”类操作
    if info.status == DiskStatus.WARNING:
        growing_ops = (
            "download", "dataset", "extract", "unzip", "train", "install",
            "模型", "数据集", "下载", "解压", "训练", "安装",
        )
        if any(k in op_name.lower() for k in growing_ops):
            return OpCheckResult(
                ok=False,
                status=info.status,
                free_gb=free_gb,
                reason=(
                    f"磁盘处于 WARNING 状态 (剩余 {free_gb:.1f}GB)。"
                    f"禁止扩大数据规模的操作 [{op_name}]。"
                ),
                policy=info.policy,
            )

    # 4) 通过检查
    return OpCheckResult(
        ok=True,
        status=info.status,
        free_gb=free_gb,
        reason=f"空间检查通过, 允许执行 [{op_name}] (剩余 {free_gb:.1f}GB)。",
        policy=info.policy,
    )


# ---------------------------------------------------------------------------
# 便捷 CLI
# ---------------------------------------------------------------------------
def _main() -> int:
    drive = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DRIVE
    info = get_disk_info(drive)
    print(f"Drive            : {info.drive}")
    print(f"Total            : {info.total_gb:.2f} GB")
    print(f"Used             : {info.used_gb:.2f} GB")
    print(f"Free             : {info.free_gb:.2f} GB")
    print(f"Status           : {info.status}")
    print(f"Policy           : {info.policy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
