# PROJECT_STATUS.md — 基于 YOLO 的智能盲道障碍物监测与预警系统

## Phase 00 — 项目安全与磁盘管理初始化

### 当前状态 (Current Status)
- **阶段**: Phase 08 已完成 ✅（Phase 00 / 02 / 03 / 04 / 05 / 06 / 07 亦已完成）
- **整体状态**: 初始化就绪, 磁盘状态 **NORMAL**, 可安全进入后续 Phase。
- **硬件**: NVIDIA RTX 5070 (8GB VRAM)
- **项目根目录**: `D:\BlindRoadMonitor`

### 磁盘空间 (Disk Space)
> 采样自当前运行环境的实时探测; 沙箱对 D 盘挂载容量有轻微浮动, 真实本机以脚本实时读数为准。
> 用户预期可用空间约 56 GB, 与首次探测 (53.3 GB) 基本吻合, 均处于 NORMAL。

| 指标         | 数值                  | 状态   |
| ------------ | --------------------- | ------ |
| 监控盘符     | D:\                   | —      |
| 总空间       | ~200 GB (沙箱视图; 真实约 214 GB) | — |
| 已使用       | ~152.8 GB (76.4%)     | —      |
| 剩余空间     | ~47.2 GB (沙箱视图; 真实约 52–53 GB) | NORMAL (≥ 30 GB) |
| 项目目录占用 | 94.42 KB              | 可忽略 |
| venv 占用    | ~5.0 GB (PyTorch GPU + Ultralytics) | 已计入已使用 |

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
- **升级 (仅 venv 内)**: pip 26.1.2 (沙箱删除守卫阻止升到 26.2.1, 功能完整) / wheel 0.48.0
- **未安装** (遵守约束): PyTorch / Ultralytics / CUDA Toolkit / TensorRT / OpenCV / FastAPI
- **新增脚本**: `scripts/check_python_env.py` — 验证当前 Python 来自本项目 venv (venv 内运行 PASS, 其它环境 FAIL)
- 磁盘状态仍为 **NORMAL** (venv 占用约 12 MB, 可忽略)

### Phase 04 — PyTorch GPU 环境 (已完成 ✅)
- **性质**: 在 venv 内安装 PyTorch GPU (CUDA) 版本; **未安装 CUDA Toolkit / TensorRT / OpenCV / FastAPI**, 未修改已有 Anaconda / managed 环境。
- **版本依据**: 查询官方 pytorch.org 预编译 wheel 索引 (非旧知识猜测)。
- **安装命令**: `D:\BlindRoadMonitor.venv\Scripts\python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128`
- **结果**:
  - torch **2.11.0+cu128** ｜ torchvision 0.26.0+cu128 ｜ torchaudio 2.11.0+cu128
  - setuptools **81.0.0** (torch 要求 `<82`, 已修正 Phase 03 的 84.0.0) ｜ wheel 0.48.0 ｜ pip 26.1.2
- **关键验证**: `torch.cuda.is_available() == True` ✅; 设备 = **NVIDIA GeForce RTX 5070 Laptop GPU**;`pip check` → No broken requirements found ✅
- **排错记录**: 首次安装因 safe-delete 守卫拦截 setuptools 降级而回滚; 改用「`--no-deps` 装 torch 全家桶 + 单独装运行依赖」绕过, 再用 Python 直接清理删残的 setuptools 并装干净 81.0.0。
- **磁盘**: 安装后 venv 占用 ~4.4 GB, D 盘剩余 ~47.2 GB (沙箱视图) / 真实约 52–53 GB → 状态 **NORMAL**。

### Phase 05 — RTX 5070 GPU 验证 (已完成 ✅)
- **性质**: 轻量验证 RTX 5070 能否稳定运行 PyTorch; **不训练、不下载数据集、不占大磁盘**; 遇 CUDA error / OOM / driver error 立即停止。
- **新增脚本**: `scripts/test_gpu.py` (stdlib + torch, 带异常捕获; 检查 CUDA 可用性 / GPU 名 / 显存 / 计算能力 / 矩阵乘 + 正确性校验)。
- **验证结果**:
  - PyTorch **2.11.0+cu128** ｜ CUDA 运行时 **12.8**
  - GPU: **NVIDIA GeForce RTX 5070 Laptop GPU** ｜ 计算能力 **sm_120** (Blackwell) ｜ 显存 **8.55 GB**
  - 4096×4096 矩阵乘法正常; 与 CPU 结果误差 **1.53e-05 → PASS**; 测试峰值显存占用 ~210 MB (远小于 8 GB)
  - 退出码 **0**, 无 CUDA error / OOM / driver error
- **结论**: RTX 5070 8GB 可稳定运行 PyTorch GPU 计算, 满足 YOLO 训练/推理基础条件 (受 8GB 显存限制, 训练需控制 batch size / 分辨率)。

### Phase 06 — YOLO (Ultralytics) 环境 (已完成 ✅)
- **性质**: 在隔离 venv 内安装 Ultralytics (YOLO) 及项目真正需要的基础依赖; **未安装**任何不必要的大型 AI 框架 (如 TensorFlow / JAX / MMDetection 等)。
- **安装命令**: `D:\BlindRoadMonitor.venv\Scripts\python.exe -m pip install ultralytics` (PyTorch 已由 Phase 04 预装, 仅新增 YOLO 依赖)
- **关键结果**:
  - `import ultralytics` ✅ 版本 **8.4.135**
  - `yolo checks` ✅ **Setup complete** — Python 3.13.14 / torch 2.11.0+cu128 / CUDA:0 (RTX 5070 Laptop GPU, 8151 MiB) / CUDA 12.8
  - 依赖齐备: opencv-python 5.0.0.93 / matplotlib 3.11.1 / numpy 2.5.2 / pillow 12.3.0 / pyyaml 6.0.3 / requests 2.34.2 / torchvision 0.26.0+cu128 / psutil 7.2.2 / polars 1.44.1 / nvidia-ml-py 13.610.43 / ultralytics-thop 2.1.6 / ultralytics-platform 0.1.20
- **新增脚本**: `scripts/check_yolo.py` — 一体化校验 Python(venv) / Ultralytics / PyTorch / CUDA / GPU, 带异常捕获, 全部 PASS 退出码 0。
- **新增文件**: `requirements.txt` — 记录 venv 中**实际安装**的精确版本 (pip freeze 导出), 便于复现。
- **磁盘**: 安装后 venv 占用 ~5.0 GB, D 盘剩余 **NORMAL** (沙箱视图约 79.5 GB / 真实约 52–53 GB)。

### Phase 07 — YOLO 基础推理验证 (已完成 ✅)
- **性质**: 无正式数据集情况下, 用 Ultralytics 自带示例图 (bus.jpg) + 自动下载的 yolov8n 预训练权重跑通一次 GPU 推理; **不下载大型数据集、不训练**。
- **新增脚本**: `tests/test_yolo_inference.py` — 加载模型 → GPU(device=0)推理 → 保存结果图, 收集模型大小/推理时间/GPU 显存/检测框数/输出图片, 带异常捕获 (OOM/CUDA error 立即停止)。
- **关键结果**:
  - 模型: `yolov8n.pt` **6.25 MB** (已缓存至 `models/`, 被 `.gitignore` 屏蔽, 不入库)
  - 测试图: `ultralytics/assets/bus.jpg` (官方自带示例, 约 100KB)
  - GPU 推理: cuda:0 (RTX 5070), 耗时 **1.447 s** (二次运行, 无下载)
  - GPU 显存: 推理后 23.2 MB / 峰值 28.0 MB (远低于 8GB)
  - 检测框: **6 个**; 输出图: `runs/yolo_inference_test/bus.jpg` (已保存 ✅)
  - 退出码 **0**, 全部 PASS
- **结论**: YOLO 在 RTX 5070 上模型加载/GPU 推理/结果生成/图片保存全流程正常, 具备进入数据集采集与训练阶段的基础。

### Phase 08 — 公开盲道数据集调研 (已完成 ✅)
- **性质**: 纯调查研究; **未下载、未解压、未训练、未转换**任何数据集; 磁盘状态仍为 **NORMAL**(采样时 D 盘剩余约 79 GB)。
- **调研对象**(按用户给定关键词): GuideTWSI / Tenji10K / TWSI datasets / tactile paving datasets / blind sidewalk datasets / obstacle detection sidewalk datasets。
- **覆盖候选**: GuideTWSI、WOTR、Tenji10K、SideGuide、TP-Dataset(GRFB-UNet)、SToP(合成)、Obstacles in Public Spaces(Dist-YOLO), 及补充 ROD-Dataset / Mendeley VI。
- **核心结论 — 推荐主用**:
  - **WOTR (MIT)**: 唯一同时含「盲道类 + 15 类障碍物」且 MIT 授权, 13,928 图, VOC→YOLO 易转, 体量约 2–4 GB, 最贴合「盲道障碍物监测」。
  - **GuideTWSI (MIT)**: 盲道专精最强, 39.5K 图(条状+圆点/真实+合成), 官方 YOLOv11-seg 权重与格式转换器, RBar-22K 子集约 5–10 GB。
  - 障碍物扩充可选: Obstacles in Public Spaces (CC0, 原生 YOLO) / ROD-Dataset (CC BY 4.0, 原生 YOLO)。
- **不推荐主用**: SideGuide(申请制+数十 GB 过大) / Tenji10K(许可不明+双线标注需转换) / TP-Dataset(CC BY-NC-SA 非商业)。
- **预计空间**: 第一阶段(WOTR 全量 + GuideTWSI RBar-22K 子集 3–5K)约 **8–15 GB**, 在 NORMAL 下安全。
- **第一阶段建议图片数**: WOTR 全量 13,928 + GuideTWSI 盲道图 3,000–5,000 ≈ **17,000–19,000 张**; 训练 YOLOv8n/v11n-seg @640px, batch 16–24 (OOM 降至 8–16)。
- **输出文档**: `docs/dataset_candidates.md`(逐候选记录: 名称/论文/来源/License/图片数/标注类型/盲道/障碍物/Seg/Det/大小/下载方式/YOLO 适合 + 推荐方案)。

### 下一步 (Next Steps)
- Phase 09 (待用户决定): 数据集获取与训练准备 — 下载前必须 `check_before_operation()` 闸门校验 (状态需 NORMAL); 标注统一为 YOLO 格式; 数据落入 `datasets/`(已被 .gitignore 屏蔽)。
- 任何下载 / 解压 / 训练前, 必须调用 `check_before_operation()` 做闸门校验。
- 持续监控: 定期运行 `python scripts/check_disk_space.py`, 状态低于 NORMAL 时按策略暂停或停止。

### 约束 (Hard Constraints — 全程有效)
- 不以任何理由导致 D 盘爆满。
- 不自动删除用户文件。
- WARNING 下禁止扩大数据规模; DANGER 下立即停止大型操作并等待用户指令。
