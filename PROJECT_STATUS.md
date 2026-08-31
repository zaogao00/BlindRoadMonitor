# PROJECT_STATUS.md — 基于 YOLO 的智能盲道障碍物监测与预警系统

## Phase 00 — 项目安全与磁盘管理初始化

### 当前状态 (Current Status)
- **阶段**: Phase 03 已完成 ✅（Phase 00 / 02 亦已完成）
- **整体状态**: 初始化就绪, 磁盘状态 **NORMAL**, 可安全进入后续 Phase。
- **硬件**: NVIDIA RTX 5070 (8GB VRAM)
- **项目根目录**: `D:\BlindRoadMonitor`

### 磁盘空间 (Disk Space)
> 采样自当前运行环境的实时探测; 沙箱对 D 盘挂载容量有轻微浮动, 真实本机以脚本实时读数为准。
> 用户预期可用空间约 56 GB, 与首次探测 (53.3 GB) 基本吻合, 均处于 NORMAL。

| 指标         | 数值                  | 状态   |
| ------------ | --------------------- | ------ |
| 监控盘符     | D:\                   | —      |
| 总空间       | ~200 GB               | —      |
| 已使用       | ~150.4 GB (75.2%)     | —      |
| 剩余空间     | ~49.6 GB              | NORMAL (≥ 30 GB) |
| 项目目录占用 | 10.73 KB              | 可忽略 |

**阈值**: NORMAL ≥ 30 GB ｜ WARNING 15~30 GB ｜ DANGER < 15 GB

### 已完成内容 (Completed in Phase 00)
1. ✅ 创建项目目录树:
   `scripts / docs / datasets / models / runs / backend / frontend / tests / configs`
2. ✅ `scripts/disk_manager.py` — 磁盘管理模块 (stdlib-only):
   - `get_disk_info()` 获取盘符用量与状态
   - `get_dir_size()` 递归计算目录占用
   - `check_before_operation()` 大型操作前空间闸门 (NORMAL/WARNING/DANGER)
3. ✅ `scripts/check_disk_space.py` — 磁盘空间检查 CLI (输出总/已用/剩余/状态/项目占用, 支持 `--json`)
4. ✅ `docs/storage_report.md` — 存储与磁盘安全报告
5. ✅ `PROJECT_STATUS.md` — 本文件
6. ✅ `.git` 初始化 (commit: `Phase 00: project safety initialization`)
7. ✅ 落实操作约束: 未安装任何 Python 包 / 未下载数据集 / 未安装 CUDA·PyTorch / 未训练 / 未删除任何用户文件

### Phase 02 — 开发环境检查 (已完成 ✅)
- **性质**: 纯只读检查, 未安装 / 卸载 / 升级任何组件, 未修改已有 Python 环境。
- **Windows**: Windows 11 家庭版 中文版 (10.0.26200, Build 26200, 64 位)
- **CPU**: AMD Ryzen 9 8940HX with Radeon Graphics, 16 核 / 32 线程
- **内存**: 约 16 GB (15.2 GiB)
- **GPU (目标)**: NVIDIA GeForce RTX 5070 Laptop GPU, 8 GB VRAM (8151 MiB)
- **NVIDIA 驱动**: 591.86 (WDDM 32.0.15.9186); 驱动支持 CUDA 最高 **13.1**
- **CUDA Toolkit**: **未安装** (符合 Phase 00 约束); 详见 `docs/environment.md`
- **Python**: 3.13.14 (managed, 路径 `C:\Users\ZaogaoLE\.workbuddy\binaries\python\versions\3.13.12\python.exe`)
- **⚠️ pip 错位**: 裸 `pip` 指向 Anaconda, `python -m pip` 才指向 managed 环境; Phase 01 **必须**用 `python -m pip` 并在独立 venv 中安装
- **py Launcher**: 未安装 (`py --list` 不可用)
- **Git**: 2.55.0.windows.3
- **磁盘**: D:\ 剩余 ~49.6 GB → 状态 **NORMAL**
- 输出文档: `docs/environment.md`

### Phase 03 — 隔离 Python 虚拟环境 (已完成 ✅)
- **性质**: 创建隔离 venv, 仅 `python -m venv`, 未使用/修改任何已有环境 (Anaconda / managed 均不动)。
- **venv 路径**: `D:\BlindRoadMonitor.venv`
- **解释器**: `D:\BlindRoadMonitor.venv\Scripts\python.exe` (Python 3.13.14, base = managed 3.13.12)
- **升级 (仅 venv 内)**: pip 26.1.2 (沙箱删除守卫阻止升到 26.2.1, 功能完整) / setuptools 84.0.0 / wheel 0.48.0
- **未安装** (遵守约束): PyTorch / Ultralytics / CUDA Toolkit / TensorRT / OpenCV / FastAPI
- **新增脚本**: `scripts/check_python_env.py` — 验证当前 Python 来自本项目 venv (venv 内运行 PASS, 其它环境 FAIL)
- 磁盘状态仍为 **NORMAL** (venv 占用约 12 MB, 可忽略)

### 下一步 (Next Steps)
- Phase 01 (待用户决定): 环境搭建 — 在隔离 venv 中安装 PyTorch / CUDA (需先再次确认磁盘状态 NORMAL)。
- 任何下载 / 解压 / 训练前, 必须调用 `check_before_operation()` 做闸门校验。
- 持续监控: 定期运行 `python scripts/check_disk_space.py`, 状态低于 NORMAL 时按策略暂停或停止。

### 约束 (Hard Constraints — 全程有效)
- 不以任何理由导致 D 盘爆满。
- 不自动删除用户文件。
- WARNING 下禁止扩大数据规模; DANGER 下立即停止大型操作并等待用户指令。
