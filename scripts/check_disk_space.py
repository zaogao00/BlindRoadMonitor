#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_disk_space.py — 检查 D 盘磁盘空间与项目占用 (stdlib only)

输出:
  - D 盘总空间
  - D 盘已使用
  - D 盘剩余
  - 当前状态 (NORMAL / WARNING / DANGER)
  - 项目占用 (D:\\BlindRoadMonitor 目录大小)

用法:
  python check_disk_space.py
  python check_disk_space.py --json        # 以 JSON 输出, 便于被其它脚本解析
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# 让脚本无论被哪里调用都能 import 到同目录下的 disk_manager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from disk_manager import (  # noqa: E402
    DEFAULT_DRIVE,
    DiskStatus,
    STATUS_POLICY,
    format_size,
    get_dir_size,
    get_disk_info,
)

# 项目根目录 (scripts/ 的上一级)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_report(drive: str = DEFAULT_DRIVE, project_root: str = PROJECT_ROOT) -> dict:
    info = get_disk_info(drive)
    project_size = get_dir_size(project_root)
    used_pct = (info.used_bytes / info.total_bytes * 100.0) if info.total_bytes else 0.0
    return {
        "drive": info.drive,
        "total_gb": round(info.total_gb, 2),
        "used_gb": round(info.used_gb, 2),
        "used_percent": round(used_pct, 1),
        "free_gb": round(info.free_gb, 2),
        "status": info.status,
        "policy": STATUS_POLICY[info.status],
        "project_root": project_root,
        "project_size_bytes": project_size,
        "project_size_human": format_size(project_size),
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="Check D: disk space and project usage.")
    parser.add_argument("--drive", default=DEFAULT_DRIVE, help="Drive letter to check (default D:\\)")
    parser.add_argument("--project-root", default=PROJECT_ROOT, help="Project root path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    report = build_report(args.drive, args.project_root)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=" * 52)
    print("  磁盘空间检查 / Disk Space Check")
    print("=" * 52)
    print(f"  磁盘 (Drive)        : {report['drive']}")
    print(f"  总空间 (Total)       : {report['total_gb']:.2f} GB")
    print(f"  已使用 (Used)        : {report['used_gb']:.2f} GB ({report['used_percent']:.1f}%)")
    print(f"  剩余 (Free)          : {report['free_gb']:.2f} GB")
    print(f"  当前状态 (Status)    : {report['status']}")
    print(f"  状态策略 (Policy)    : {report['policy']}")
    print("-" * 52)
    print(f"  项目根目录           : {report['project_root']}")
    print(f"  项目占用 (Project)   : {report['project_size_human']} ({report['project_size_bytes']} bytes)")
    print("=" * 52)

    # 非 NORMAL 状态给出醒目提示
    if report["status"] != DiskStatus.NORMAL:
        print(f"  ⚠ 注意: 当前状态为 {report['status']}, 请遵循上述策略。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
