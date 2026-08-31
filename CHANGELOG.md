# CHANGELOG

本项目所有重要变更记录于此。格式参考 Keep a Changelog。

## [Phase 03] — 2026-08-31

### Added (新增)
- 隔离 Python 虚拟环境: `D:\BlindRoadMonitor.venv` (基于 managed Python 3.13.14, 未用 Anaconda / 其它杂乱环境)
- `scripts/check_python_env.py`: 验证当前 Python 是否来自本项目 venv (stdlib-only; venv 内 PASS / 其它 FAIL, 退出码 0/1)

### Upgraded (仅 venv 内)
- setuptools 84.0.0 (最新)
- wheel 0.48.0 (最新)
- pip 26.1.2 (沙箱 safe-delete 守卫拦截对 `Scripts/pip.exe` 的覆盖, 未能升到 26.2.1; 功能完整, 不影响后续安装)

### Not Installed (遵守约束, 未安装)
- PyTorch / Ultralytics / CUDA Toolkit / TensorRT / OpenCV / FastAPI

### Disk (磁盘状态)
- 当前状态: **NORMAL** (D 盘剩余 ≥ 30 GB); venv 占用约 12 MB, 可忽略

### Git
- 提交: `Phase 03: isolated Python environment`

## [Phase 02] — 2026-08-31

### Checked (只读检查, 未修改环境)
- Windows 11 家庭版 中文版 (10.0.26200, Build 26200, 64 位)
- CPU: AMD Ryzen 9 8940HX with Radeon Graphics, 16 核 / 32 线程; 内存约 16 GB (15.2 GiB)
- GPU: NVIDIA GeForce RTX 5070 Laptop GPU, 8 GB VRAM (8151 MiB); 驱动 591.86 (支持 CUDA 最高 13.1)
- CUDA Toolkit: 未安装 (符合 Phase 00 约束); 报告中的 "CUDA 13.1" 为驱动能力上限, 非已装 Toolkit
- Python 3.13.14 (managed); 裸 `pip` 指向 Anaconda, `python -m pip` 才指向 managed 环境 — 已记录错位风险
- py Launcher 未安装 (`py --list` 不可用); Git 2.55.0.windows.3
- 磁盘: D:\ 剩余 ~49.6 GB → 状态 NORMAL

### Added
- `docs/environment.md`: 环境检查报告 (Windows / CPU / 内存 / GPU / 驱动 / CUDA / Python / pip / Git / 磁盘)

### Safety (安全约束落实)
- 仅检查环境, 未安装 / 卸载 / 升级任何组件
- 未修改已有 Python 环境, 未安装 CUDA Toolkit / PyTorch, 未升级 NVIDIA 驱动

## [Phase 00] — 2026-08-31

### Added (新增)
- 项目目录树: `scripts / docs / datasets / models / runs / backend / frontend / tests / configs`
- `scripts/disk_manager.py`: 磁盘安全管理模块 (标准库实现, 无第三方依赖)
  - `get_disk_info()` — 获取磁盘总/已用/剩余空间与 NORMAL/WARNING/DANGER 状态
  - `get_dir_size()` — 递归计算目录占用 (忽略符号链接, 防重复计数)
  - `check_before_operation()` — 大型操作 (下载/解压/训练/安装) 前的空间闸门
- `scripts/check_disk_space.py`: 磁盘空间检查 CLI, 输出 D 盘总量/已用/剩余/状态/项目占用, 支持 `--json`
- `docs/storage_report.md`: 存储与磁盘安全策略报告
- `PROJECT_STATUS.md`: 项目阶段状态总览

### Safety (安全约束落实)
- 未安装任何 Python 包 (纯标准库)
- 未下载数据集
- 未安装 CUDA / PyTorch
- 未执行训练
- 未删除任何已有用户文件

### Disk (磁盘状态)
- 当前状态: **NORMAL** (D 盘剩余 ≥ 30 GB)
- 项目占用: ~10.7 KB (几乎可忽略)
- 注: 运行环境对 D 盘挂载容量存在轻微浮动, 真实本机以脚本实时读数为准; 用户预期可用约 56 GB。

### Git
- 初始化仓库并提交: `Phase 00: project safety initialization`
