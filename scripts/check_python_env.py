#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_python_env.py

验证「当前正在运行的 Python」是否来自本项目的独立虚拟环境
D:\\BlindRoadMonitor.venv。

设计原则（与 Phase 03 一致）：
- 仅使用标准库（os / sys），无第三方依赖。
- 不修改任何环境，只读自检。
- 通过退出码表达结果：0 = 通过，1 = 失败。

判定逻辑：
1. 项目的 venv 路径 = 项目根目录的同级 .venv
   （项目根 = 本脚本所在目录的上一级 => D:\\BlindRoadMonitor，
    对应 venv 为 D:\\BlindRoadMonitor.venv）。
2. 当前解释器的 sys.prefix 必须指向该 venv 目录。
3. 当前解释器的 sys.executable 必须位于该 venv 目录之下。
4. venv 必须是「隔离」的：sys.base_prefix != sys.prefix，
   且其 base 不应是 Anaconda / 其他杂乱环境。
"""

import os
import sys


def resolve_project_root() -> str:
    """本脚本位于 <root>/scripts/check_python_env.py，故根目录为 scripts 的上一级。"""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    return root


def resolve_expected_venv(project_root: str) -> str:
    """venv 与项目根目录同级，命名为 <root_name>.venv。"""
    root_name = os.path.basename(project_root.rstrip(os.sep))
    parent = os.path.dirname(project_root.rstrip(os.sep))
    return os.path.join(parent, root_name + ".venv")


def is_anaconda(base_prefix: str) -> bool:
    markers = ["anaconda", "conda", "miniconda"]
    low = base_prefix.lower().replace("/", "\\")
    return any(m in low for m in markers)


def main() -> int:
    project_root = resolve_project_root()
    expected_venv = resolve_expected_venv(project_root)

    print("=" * 60)
    print("Python 环境归属自检 (check_python_env)")
    print("=" * 60)
    print(f"项目根目录      : {project_root}")
    print(f"期望 venv 路径  : {expected_venv}")
    print("-" * 60)
    print(f"sys.executable  : {sys.executable}")
    print(f"sys.prefix      : {sys.prefix}")
    print(f"sys.base_prefix : {sys.base_prefix}")
    print(f"Python 版本     : {sys.version.splitlines()[0]}")
    print("=" * 60)

    checks = []

    # 1) venv 目录存在
    venv_exists = os.path.isdir(expected_venv)
    checks.append(("venv 目录存在", venv_exists))

    # 2) sys.prefix 指向 venv
    prefix_ok = os.path.abspath(sys.prefix) == os.path.abspath(expected_venv)
    checks.append(("sys.prefix 指向 venv", prefix_ok))

    # 3) sys.executable 位于 venv 之下
    exe_ok = os.path.abspath(sys.executable).startswith(
        os.path.abspath(expected_venv) + os.sep
    )
    checks.append(("sys.executable 位于 venv 内", exe_ok))

    # 4) 隔离性：是 venv（base != prefix），且 base 非 Anaconda
    is_venv = sys.base_prefix != sys.prefix
    base_clean = not is_anaconda(sys.base_prefix)
    checks.append(("运行于虚拟环境 (非 base)", is_venv))
    checks.append(("base 环境非 Anaconda", base_clean))

    print("\n判定结果：")
    all_ok = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        all_ok = all_ok and ok

    print("=" * 60)
    if all_ok:
        print("✅ 通过：当前 Python 来自隔离的 venv", expected_venv)
        return 0
    print("❌ 失败：当前 Python 并非来自本项目的隔离 venv。")
    print("   请先激活环境：")
    print(f'     {expected_venv}\\Scripts\\activate')
    print("   或显式调用：")
    print(f'     {expected_venv}\\Scripts\\python.exe <你的脚本>')
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
