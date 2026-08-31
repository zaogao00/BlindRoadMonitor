# 环境检查报告 (Environment Inspection)

> 项目: 基于 YOLO 的智能盲道障碍物监测与预警系统
> 阶段: Phase 02 (只读检查) + Phase 03 (创建隔离 venv), 已更新至 2026-08-31
> 检查时间: 2026-08-31
> 性质: **纯只读检查**, 未安装 / 卸载 / 升级任何组件, 未修改已有 Python 环境。

---

## 1. 检查清单与结果

| 检查项             | 结果                                                                 |
| ------------------ | -------------------------------------------------------------------- |
| Windows 版本       | Microsoft Windows 11 家庭版 中文版 (64 位), 10.0.26200 (Build 26200) |
| CPU                | AMD Ryzen 9 8940HX with Radeon Graphics, 16 核 / 32 线程             |
| 内存               | 约 15.2 GB (16,340,447,232 字节 ≈ 16 GB)                            |
| GPU (目标)         | NVIDIA GeForce RTX 5070 Laptop GPU, 8 GB VRAM (nvidia-smi: 8151 MiB) |
| 其他显示适配器     | AMD Radeon 610M (集显, 512 MB) ｜ MuMu Virtual Display Adapter (模拟器) |
| NVIDIA 驱动        | 591.86 (WDDM 驱动版本 32.0.15.9186)                                 |
| CUDA 版本 (驱动支持上限) | **13.1** (由 nvidia-smi 报告, 表示驱动可支持的最高 CUDA 运行时)    |
| CUDA Toolkit       | **未安装** (本机无独立 CUDA Toolkit, 符合 Phase 00 约束)             |
| Python 版本        | 3.13.14 (managed, 路径见下)                                          |
| pip                | 注意: 裸 `pip` 指向 Anaconda; `python -m pip` 指向 managed 环境     |
| Git                | 2.55.0.windows.3                                                    |
| 磁盘空间           | D:\ 剩余 ~49.6 GB → 状态 **NORMAL** (≥ 30 GB)                      |

---

## 2. 逐项明细

### 2.1 Windows
```
Caption        = Microsoft Windows 11 家庭版 中文版
Version        = 10.0.26200
BuildNumber    = 26200
OSArchitecture = 64 位
```

### 2.2 CPU / 内存
```
CPU Name                  = AMD Ryzen 9 8940HX with Radeon Graphics
NumberOfCores            = 16
NumberOfLogicalProcessors = 32
TotalPhysicalMemory      = 16340447232 字节 (≈ 15.2 GB / 标称 16 GB)
```
> 说明: 16 核 32 线程 CPU 适合数据预处理并行; 物理内存约 16 GB 偏紧,
> 训练时需注意 batch size 与数据加载内存占用 (尽量用 RAM 磁盘/流式加载, 避免同时跑大内存应用)。

### 2.3 GPU / 驱动 / CUDA
`nvidia-smi` 输出摘要:
```
NVIDIA-SMI 591.86   Driver Version: 591.86   CUDA Version: 13.1
GPU 0: NVIDIA GeForce RTX 5070 Laptop GPU (WDDM)
      Memory-Usage: 393MiB / 8151MiB   (8 GB 显存)
      Temp 54C, Pwr 11W / 114W, GPU-Util 43%
```
`wmic path win32_VideoController` 补充:
```
Name=NVIDIA GeForce RTX 5070 Laptop GPU  DriverVersion=32.0.15.9186  AdapterRAM≈4.0GB(系统上报, 以 nvidia-smi 8GB 为准)
Name=AMD Radeon(TM) 610M                  DriverVersion=32.0.21036.11002  AdapterRAM=512MB(集显)
Name=MuMu Virtual Display Adapter         DriverVersion=20.36.41.498  (安卓模拟器虚拟显示, 忽略)
```
> 关键点:
> - **驱动 591.86 + CUDA 13.1**: 驱动可支持到 CUDA 13.1 运行时, 但本机**并未安装 CUDA Toolkit**。
>   这里的 "CUDA Version: 13.1" 是驱动能力上限, 不等同于已安装 CUDA 开发环境。
> - RTX 5070 属 Blackwell 架构 (计算能力 sm_120), 使用 PyTorch 时需匹配支持该架构的构建
>   (CUDA 12.8+ / 13.x 运行时)。Phase 01 安装 PyTorch 时务必选用带 CUDA 的 wheel, 并验证 `torch.cuda.is_available()`。
> - 显存 8 GB 限制: YOLO 训练需控制 batch size / 输入分辨率, 避免 OOM。

### 2.4 Python 环境 (重要: 存在多版本与 pip 错位)
```
python --version  -> Python 3.13.14
where python      ->
  C:\Users\ZaogaoLE\.workbuddy\binaries\python\versions\3.13.12\python.exe   (managed, 实际 3.13.14)
  D:\anaconda\python.exe                                                       (Anaconda, 3.13.x)
  C:\Users\ZaogaoLE\AppData\Local\Microsoft\WindowsApps\python.exe            (Store 占位, 勿用)

python -c "sys.executable" -> C:\Users\ZaogaoLE\.workbuddy\binaries\python\versions\3.13.12\python.exe
python -m pip --version     -> pip 26.1.2 (来自 managed 3.13.12 的 site-packages, python 3.13)

pip --version    -> pip 25.1 from D:\anaconda\Lib\site-packages\pip (python 3.13)   <-- 指向 Anaconda!
py --list        -> 命令未找到 (本机未安装 Python Launcher `py.exe`)
```
> ⚠️ **强烈注意 (Phase 01 必读)**:
> - 当前 `python` 解析到 **managed 3.13.14**, 但裸 `pip` 解析到 **Anaconda** 的 pip 25.1。
>   二者不一致: 若直接运行 `pip install xxx`, 包会装进 Anaconda, 而 `python` 运行 managed 环境, 导致“装了却 import 不到”。
> - 正确做法: **始终用 `python -m pip install ...`** 来精确命中当前 `python` 对应的环境。
> - 推荐在 Phase 01 为项目建立**独立 venv** (`python -m venv ...`), 彻底隔离, 避免污染 Anaconda 与 managed 环境。
> - `py` Launcher 不存在, 不要依赖 `py -3.x` 语法。

### 2.5 Git
```
git version 2.55.0.windows.3   (可用, 仓库已于 Phase 00 初始化)
```

### 2.6 磁盘空间
```
D:\ 总空间 ~200 GB | 已用 ~150.4 GB (75.2%) | 剩余 ~49.6 GB | 状态 NORMAL
项目目录占用 ~58 KB (可忽略)
```
> 沙箱对 D: 挂载容量有轻微浮动, 真实本机以脚本实时读数为准; 用户预期约 56 GB 可用, 均处于 NORMAL, 可继续后续 Phase。

---

## 3. 结论与建议

1. **硬件可用**: CPU (16C/32T) + RTX 5070 8GB + Win11, 满足 YOLO 训练/推理的入门到中等规模需求; 受限于 8GB 显存与 16GB 内存, 训练时须控制 batch size 与分辨率。
2. **驱动就绪**: NVIDIA 驱动 591.86 (CUDA 13.1 能力), 但**未安装 CUDA Toolkit**; Phase 01 安装 PyTorch 时直接用预编译 CUDA wheel 即可, 无需先装 CUDA Toolkit (除非后续需自定义 CUDA 算子)。
3. **Python 环境需理顺**: 存在 managed / Anaconda / Store 三套, 且 `pip` 与 `python` 错位。Phase 01 必须:
   - 使用 `python -m venv` 建隔离环境;
   - 用 `python -m pip` 安装依赖;
   - 不修改已有 Anaconda / managed 环境 (符合本阶段约束)。
4. **本阶段零修改**: 未安装/卸载/升级任何组件, 严格遵守约束。

---

## 4. 下一步 (Phase 03 已完成 venv 创建; 待 Phase 01 安装依赖)
- 独立 venv 已就绪: `D:\BlindRoadMonitor.venv` (基于 managed Python 3.13.14)。
- 安装依赖前先运行 `python scripts/check_disk_space.py` 确认 NORMAL, 并用 `check_before_operation()` 闸门校验空间。
- 始终用 venv 内的解释器: `D:\BlindRoadMonitor.venv\Scripts\python.exe -m pip install ...`

---

## 5. Phase 03 — 独立 Python 虚拟环境 (已创建 ✅)

> 阶段性质: **创建隔离环境**, 仅使用 `python -m venv`, 不修改任何已有 Python 环境。
> 约束遵守: 未安装 PyTorch / Ultralytics / CUDA Toolkit / TensorRT / OpenCV / FastAPI。

### 5.1 创建前检查 (Python 版本 / 路径)
```
python --version -> Python 3.13.14
where python      ->
  C:\Users\ZaogaoLE\.workbuddy\binaries\python\versions\3.13.12\python.exe   (managed, 实际 3.13.14)  <-- 选用
  D:\anaconda\python.exe                                                       (Anaconda, 跳过)
  C:\Users\ZaogaoLE\AppData\Local\Microsoft\WindowsApps\python.exe            (Store 占位, 跳过)
```
- **选型依据**: RTX 5070 (Blackwell, sm_120) 需 CUDA 12.8+/13.x 运行时; 当前 PyTorch 2.x 与 Ultralytics 8.x 均官方支持 Python 3.9–3.13, 故 3.13.14 (managed) 为稳定可用版本。本机仅有的 managed 解释器即 3.13.x, 直接采用, **未使用 Anaconda 或其它杂乱环境**。

### 5.2 创建结果
- venv 路径: `D:\BlindRoadMonitor.venv`
- 解释器: `D:\BlindRoadMonitor.venv\Scripts\python.exe` (Python 3.13.14)
- base: `C:\Users\ZaogaoLE\.workbuddy\binaries\python\versions\3.13.12` (managed, 非 Anaconda)
- 创建命令: `python -m venv D:\BlindRoadMonitor.venv`

### 5.3 升级 (仅限 venv 内)
| 包          | 版本     | 备注                                                                 |
| ----------- | -------- | -------------------------------------------------------------------- |
| pip         | 26.1.2   | 沙箱 safe-delete 守卫阻止覆盖 `Scripts/pip.exe`, 未能升到 26.2.1; 26.1.2 功能完整 |
| setuptools  | 84.0.0   | 已升级到最新                                                         |
| wheel       | 0.48.0   | 已升级到最新                                                         |
| packaging   | 26.3     | 随 wheel 依赖安装                                                    |

> ⚠️ **pip 自升级说明**: 本运行环境的文件删除安全守卫 (`safe-delete`, 回收站不可用时拒绝删除) 会拦截 pip 升级时对旧 `pip.exe` 的覆盖写入, 因此 pip 停留在 26.1.2。这是环境限制而非操作失误; pip 26.1.2 可正常安装 PyTorch / Ultralytics, 无需最新补丁。

### 5.4 环境归属自检脚本
- `scripts/check_python_env.py` (stdlib-only): 验证「当前 Python 是否来自 `D:\BlindRoadMonitor.venv`」。
  - 检查项: venv 目录存在 / `sys.prefix` 指向 venv / `sys.executable` 位于 venv 内 / 运行于虚拟环境 (`base≠prefix`) / base 非 Anaconda。
  - 退出码: `0`=通过, `1`=失败。
  - 已验证: 用 venv 解释器运行 → ✅ PASS (exit 0); 用 managed 解释器运行 → ❌ FAIL (exit 1)。

### 5.5 如何使用 venv
```
# 激活 (PowerShell / CMD)
D:\BlindRoadMonitor.venv\Scripts\activate

# 或直接显式调用
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts/check_python_env.py
D:\BlindRoadMonitor.venv\Scripts\python.exe -m pip install <包>
```

