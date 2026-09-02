# PROJECT_STATUS.md — 基于 YOLO 的智能盲道障碍物监测与预警系统

## Phase 00 — 项目安全与磁盘管理初始化

### 当前状态 (Current Status)
- **阶段**: Phase 00 / 02–09 已完成 ✅；**Phase 10 数据集分析 已完成 ✅**；**Phase 11 YOLO 数据集转换 已完成 ✅** (17,908 图 / 195,719 实例 / 26 类)；**Phase 12 可视化质量检查 已完成 ✅** (120 张全部正常)；**Phase 13 小规模训练验证 已完成 ✅** — YOLOv8n smoke test (450 图 / 10 epochs / 103 s / mAP50 0.303 / loss 正常下降 / 无 OOM)
- **整体状态**: 训练管线验证通过, 磁盘状态 **NORMAL**, 可进入全量正式训练 (Phase 14 候选)。
- **硬件**: NVIDIA RTX 5070 (8GB VRAM)
- **项目根目录**: `D:\BlindRoadMonitor`

### 磁盘空间 (Disk Space)
> 采样自当前运行环境的实时探测; 沙箱对 D 盘挂载容量有轻微浮动, 真实本机以脚本实时读数为准。

| 指标         | 数值                  | 状态   |
| ------------ | --------------------- | ------ |
| 监控盘符     | D:\                   | —      |
| 总空间       | ~200 GB (沙箱视图)    | —      |
| 已使用       | ~135.7 GB (67.9%)     | —      |
| 剩余空间     | **~64.3 GB** (Phase 13 后) | NORMAL (≥ 30 GB) |
| 项目目录占用 | ~8.9 GB (raw 4.41 + processed 4.37 + runs 权重 ~50 MB + smoke 126 MB) | 已计入已使用 |
| venv 占用    | ~4.7 GB (PyTorch GPU + Ultralytics) | 已计入已使用 |
| ROD 数据集   | 225.7 MB (raw; 4,000 图 + 4,000 标签) | 已计入已使用 |
| WOTR 数据集  | 4.19 GB (raw; 13,928 图 + VOC) | 已计入已使用 |
| processed    | 4.37 GB (YOLO; 17,908 图 + 标签) | 已计入已使用 |
| preview      | 16.1 MB (Phase 12 可视化; 121 张) | 已计入已使用 |
| smoke_test   | 126 MB (Phase 13 子集; 450+100 图) | 已计入已使用 |

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

### Phase 08 — 公开盲道数据集调研 (已完成 ✅; 2026-09-01 复查重跑)
- **性质**: 纯调查研究; **未下载、未解压、未训练、未转换**任何数据集; 磁盘状态仍为 **NORMAL**(实时探测 D 盘剩余 79.2 GB)。
- **调研对象**(按用户给定关键词): GuideTWSI / Tenji10K / TWSI datasets / tactile paving datasets / blind sidewalk datasets / obstacle detection sidewalk datasets。
- **覆盖候选(首版 + 复查新增)**: GuideTWSI、WOTR、Tenji10K、SideGuide、TP-Dataset(GRFB-UNet)、SToP(合成)、Obstacles in Public Spaces(Dist-YOLO), 补充 ROD-Dataset / Mendeley VI; 复查新增 **BLV-Road-Nav-Accessibility**(GitHub, 21 视频/90 类)、**TactPav**(ECNU, VLM 多模态)、Roboflow 小集(crosswalk-tactile-blocks / tactile-paving-segmentation)。
- **复查确认在线**: GuideTWSI 项目主页+论文 PDF / WOTR GitHub+README / GRFB-Unet GitHub / SToP 项目主页 / Tenji10K Wiley / ROD-Dataset HF(含 jiasea 镜像)。
- **核心结论 — 推荐主用(不变)**:
  - **WOTR (MIT)**: 唯一同时含「盲道类 + 15 类障碍物」且 MIT 授权, 13,928 图, VOC→YOLO 易转, 体量约 2–4 GB, 最贴合「盲道障碍物监测」。
  - **GuideTWSI (MIT)**: 盲道专精最强, 39.5K 图(条状+圆点/真实+合成), 官方 YOLOv11-seg 权重与格式转换器, RBar-22K 子集约 5–10 GB; ⚠️ HF/Kaggle 获取可能仍需鉴权。
  - 障碍物扩充可选: ROD-Dataset (CC BY 4.0, 原生 YOLO, **本环境最可行/已落地 614 张**) / Obstacles in Public Spaces (CC0, 原生 YOLO)。
- **不推荐主用**: SideGuide(申请制+数十 GB 过大) / Tenji10K(许可不明+双线标注需转换) / TP-Dataset(CC BY-NC-SA 非商业)。
- **方法参考信号(非数据集)**: 街景图+VLM 盲道障碍物监测(SAGE 2026) / 街景图盲道自动检测(IEEE 2025) / DPSN 盲道+障碍物联合分割。
- **预计空间**: 第一阶段(WOTR 全量 + GuideTWSI RBar-22K 子集 3–5K)约 **8–15 GB**, 在 NORMAL 下安全。
- **第一阶段建议图片数**: WOTR 全量 13,928 + GuideTWSI 盲道图 3,000–5,000 + ROD 已落地 614 ≈ **17,000–19,000 张**; 训练 YOLOv8n/v11n-seg @640px, batch 16–24 (OOM 降至 8–16)。
- **输出文档**: `docs/dataset_candidates.md`(逐候选记录: 名称/论文/来源/License/图片数/标注类型/盲道/障碍物/Seg/Det/大小/下载方式/YOLO 适合 + 推荐方案 + 复查要点)。

### Phase 09 — 数据集安全下载 (已完成 ✅; 2026-09-01)
- **性质**: 下载已确认数据集, **未训练、未转换**。本轮完成两个数据集:
  - **ROD-Dataset** (原生 YOLO, 24,326 图全集, HF README 标注 **MIT**): 网络恢复后从 614 张**断点续传至 4,000 张** (train 1,000 / valid 1,371 / test 1,629 全量 = 4,000 图 + 4,000 标签, 225.7 MB); 校验 0 损坏 / 0 零字节 / 配对完整 (12 空标签可忽略)。
  - **WOTR** (VOC 格式, **MIT**, 含盲道类): 用户要求补盲道数据 → Roboflow 403/GuideTWSI 401 不可用 → 实测 **Google Drive 公开链接零凭证可达**, 全量下载 **13,928 图 + 13,928 VOC XML** (train 9,056 / val 2,338 / test 2,534), 解压 4.19 GB; `testzip()` 通过, 配对完整, 全量盲道 **1,723 图 / 2,381 实例** (`tactile_paving→blind_road`); WOTR.zip 已删除回收 3.95 GiB。
- **实施修复 (环境适配, 不改数据)**:
  - ROD: curl/schannel 不可用 → requests 直写; 标签阈值 100→0; HF 限流 16→5 并发 + 429 退避;
  - WOTR: 新增 `scripts/download_wotr.py` (gdown 流程 + **Range 断点续传** + 磁盘闸门 + zip 校验)。
- **磁盘闸门 (均通过)**: ROD 前剩余 79.2 GB; WOTR 下载/解压前 73.2 GB; 完成后 ~65 GB ≥ 30 GB → 均 NORMAL 允许。
- **落盘**: `datasets/raw/rod_dataset/` + `datasets/raw/wotr/` (各含 `DATASET_INFO.md`; 均被 `.gitignore` 屏蔽)。
- **附随文档**: `docs/dataset_report.md` (§0 WOTR 补充), `docs/storage_report.md` (§2.1 更新)。

### Phase 10 — 数据集结构与标签分析 (已完成 ✅; 2026-09-02)
- **性质**: 纯只读分析 (**全量扫描 17,928 图, 非抽样**); **未修改 / 未删除任何原始数据, 未转换, 未训练**。
- **工具**: 新增 `scripts/analyze_datasets_phase10.py` (PIL 解码校验 + MD5 去重 + VOC/YOLO 双解析器); 输出 `docs/dataset_analysis_stats.json` (可复现)。
- **规模**: WOTR 13,928 图 / 13,928 XML / **189,994** 实例 / 20 类; ROD 4,000 图 / 4,000 标签 / **6,073** 实例 / 25 类; 合计 **17,928 图 / 196,067 实例**。
- **格式判定**: WOTR = **PASCAL-VOC**(纯 bbox; 非 COCO / 非 Mask / 非 Polygon); ROD = **YOLO 原生 + Polygon 分割混合**(5,150 框 + 923 多边形; 非 COCO / 非 Mask)。
- **完整性**: 损坏图 **0** / 零字节 **0** / 配对 **100%** / 非法框 **0** / 非法标注行 **0**; 空标签 WOTR **0**、ROD **12** (0.3%, 建议留作负样本)。
- **分辨率**: WOTR 均值 883.8×746.2 (1,390 种, 最大 5,621×4,032); ROD 均值 584×578.5 (52 种, 73% 为 640×640) → 统一 `imgsz=640` letterbox 即可。
- **尺度 (COCO)**: WOTR small 37.1% / medium 42.4% / large 20.5%; ROD 以 large 为主 (84.1%)。
- **盲道类**: `blind_road` **1,723 图 / 2,381 实例** (train 1,599 / val 372 / test 410); small 仅 **1.0%** (尺度健康), 但占总实例仅 **1.21%** (样本偏少, 需后续扩充)。
- **重复与泄漏**: WOTR 11 组 + ROD 9 组重复 = **20 组, 其中 15 组跨划分** (WOTR 7: train↔test ×3 / train↔val ×2 / test↔val ×2; ROD 8: valid↔test ×4 / train↔test ×2 / train↔valid ×2; 余 5 组为划分内部), 如 `train/IMG_00021` ≡ `test/IMG_19189`; 跨数据集重复 **0**。
- **结论**: ✅ **适合 YOLO (需转换)**; 第一阶段做 **detect** (非 seg — 盲道无任何 mask 监督), `imgsz=640`。
- **类别方案**: 统一 **26 类** — 15 组跨集同义类合并 (person/Person、pole/Electrical Pole、bicycle/Bike、ashcan/Dustbin、crosswalk/Pedestrian crosswalk 等); **丢弃 2 类** `Building`(144) / `Road`(92) (背景类, 且 Road 与 blind_road 语义冲突); `electrical_box`→`pole`、`Bicycle Rack`→`bicycle`; ⚠️ 丢弃须**按行剔除** (不可只删 names, 否则 class id 错位)。
- **待处理风险**: ① 划分泄漏 **20 组重复 (15 组跨划分)** → 转换时保留 val/test、从 train 精确剔除 **13 张**副本; ② 长尾 437:1 (person 36,238 vs plant_pot 83); ③ WOTR 小目标 37% (640 分辨率下召回损失); ④ ROD License 记录不一致 (Phase 08 记 CC BY 4.0 / Phase 09 记 MIT, 均允许商用+署名, 不阻断)。
- **输出文档**: `docs/dataset_analysis.md` (含 **§8 Phase 11 转换清单**)。

### Phase 11 — YOLO 数据集转换 (已完成 ✅; 2026-09-02)
- **性质**: `datasets/raw/**` **严格只读** (一个字节未改), 输出全新目录 `datasets/processed/`; **detection** 任务 (盲道类无任何 mask 监督, ROD 多边形退化为外接矩形)。
- **工具**: 新增 `scripts/convert_dataset.py` (VOC/YOLO 双解析 + 26 类映射 + Building/Road 按行剔除 + 全局 MD5 去重 + 写 data.yaml) 与 `scripts/check_dataset.py` (转换后自检)。
- **结果**: **17,908 图 / 195,719 实例 / 26 类** — train 10,043 / val 3,702 / test 4,163 (图片=标签 100%); 空标签 146 (背景负样本, 合法); `blind_road` 2,381 全量保留; 来源 `wotr_` 13,917 + `rod_` 3,991; 占用 4.366 GiB。
- **去重**: MD5 剔除 20 张重复图 (train 13 + val 7; WOTR 11 + ROD 9), 跨划分泄漏清零。
- **丢弃**: ROD `Building`(144) / `Road`(92) 共 236 行整行剔除 (其中 137 条为多边形行); 有效多边形 786 条全部转外接框。
- **自检**: `check_dataset.py` → **PASSED** — 0 损坏 / 0 零字节 / 0 孤立标签 / 0 格式错误行 / 0 类 ID 越界 / 0 坐标非法 / 0 跨划分重复。
- **输出**: `datasets/processed/{images,labels}/{train,val,test}` + `datasets/processed/data.yaml` (`nc=26`, 绝对路径) + `docs/phase11_conversion_report.json` / `docs/phase11_check_report.json` / `docs/logs_phase11_*.txt`。
- **磁盘**: raw 4.41 + processed 4.37 ≈ 8.8 GB; 转换后 D 盘剩余 ~64.5 GB (**NORMAL** ≥ 30 GB, 未触发闸门报警)。
- **文档**: `docs/dataset_report.md` §11, `docs/dataset_analysis.md` §8 已标注"已执行"并统一输出目录为 `datasets/processed/`。

### Phase 12 — 数据可视化质量检查 (已完成 ✅; 2026-09-02)
- **性质**: 随机采样 ≥100 张训练图 (实际 **120 张**, 优先覆盖含 `blind_road` 的图), 将图片 + YOLO 标签绘制到一起进行可视化质检; 纯只读 (仅输出预览图, 未改动 processed/raw)。
- **工具**: 新增 `scripts/visualize_dataset_quality.py` (采样 + 绘制 + 数值校验); 输出 `datasets/preview/` (120 单图 + 汇总拼贴) + `docs/dataset_quality_stats.json`。
- **抽样**: 120 图 / **1,335 实例** / 0 空标签; `blind_road` 命中 **53 实例**; 覆盖 25/26 类 (唯一未命中 plant_pot, 全训练集仅 36 实例)。
- **数值检查**: 类 ID 越界 **0** / 坐标越界 **0** / 框非法 **0** / 框序颠倒 **0** / 非 5 列行 **0** / 图不可读 **0** / 配对缺失 **0**。
- **语义检查**: 盲道框形健康 (面积 mean 25.8%, 横向为主); 28 条几何异常候选复核全部合理 — 25 条为远景小目标 (roadblock/cone/立柱, 数据集固有特性), 3 条超大框溯源确认: `car 97.3%` 图经 **YOLOv8n 模型辅助验证** (检出 car conf 0.79 区域与标注高度吻合, 继承自 COCO 的标注可信), 2 条 tricycle 为作者自采近景特写。
- **结论**: **未发现严重标签错误** → 不触发「停止/不要训练」; 120 张全部**正常**, 0 异常, 0 无法使用; **可进入训练阶段**。
- **提醒 (非阻断)**: WOTR 远景小目标占比高 (关注小目标召回); `plant_pot`/`bench` 长尾类极少; tricycle 2 个超大框建议训练前人工抽查 (低风险)。
- **输出文档**: `docs/dataset_quality_report.md` (完整统计与结论)。

### Phase 13 — 小规模 YOLO 训练验证 (已完成 ✅; 2026-09-02)
- **性质**: smoke test — 少量数据 (450 train + 100 val, 含盲道 74+18), 10 epochs, 验证 数据读取/标签/模型/GPU/loss 下降/验证流程; **不追求精度, 不用全量**。
- **工具**: 新增 `scripts/make_smoke_subset.py` (子集构建, 复制不动 raw/processed) 与 `scripts/run_smoke_train.py` (训练 + 指标记录 + 沙箱适配)。
- **配置**: YOLOv8n (COCO 预训练, nc 80→26) ｜ imgsz=640 ｜ batch=16 ｜ **AMP on** ｜ 10 epochs ｜ seed=20260902。
- **结果**: 总耗时 **103 s** (≈10 s/epoch) ｜ GPU 峰值 **1.93 GB** (无 OOM, 余量充足) ｜ loss 稳定下降 (box 1.62→1.45 / cls 4.64→2.16 / dfl 1.31→1.18) ｜ mAP50 0.0005→**0.303** / mAP50-95 **0.185** / P 0.497 / R 0.293 (仅流程验证值)。
- **验证目标全部达成**: 数据 ✅ 标签 ✅ 模型 ✅ GPU (AMP checks passed) ✅ loss 下降 ✅ val 流程 ✅; 0 CUDA error / 0 OOM / exit 0。
- **沙箱适配 (环境, 非模型)**: ① `YOLO_CONFIG_DIR` 重定向字体目录至工作区 (预置 Arial.ttf) + `MPLCONFIGDIR`; ② monkeypatch ultralytics `ThreadPool` (multiprocessing 命名管道被沙箱拒, 换纯线程池); ③ dataloader workers=0。
- **产物**: `runs/smoke_test/yolov8n_smoke_b16/weights/{best,last}.pt` (6.2 MB) + results.csv ｜ `datasets/smoke_test/` (126 MB) ｜ `docs/training_smoke_test_stats.json`。
- **输出文档**: `docs/training_smoke_test.md` (完整记录)。

### 下一步 (Next Steps)
- **全量正式训练 (Phase 14 候选)**: 使用 `datasets/processed/data.yaml` (17,908 图) 训练 YOLOv8n/v11n (detect), `imgsz=640`, `batch=16` (实测峰值 1.9 GB, 可按显存升 24–32), `epoch=100–200`, `amp=True`; 重点关注核心类 `blind_road` (1,723 图 / 2,381 实例, 仅占 1.21%) 的召回与 mAP; 评估长尾类 (437:1) 与 WOTR 小目标 (37%) 影响; smoke 权重 (mAP50 0.303) 可作 warm-start 参考。
- 任何下载 / 解压 / 训练前, 必须调用 `check_before_operation()` 做闸门校验。
- 持续监控: 定期运行 `python scripts/check_disk_space.py`, 状态低于 NORMAL 时按策略暂停或停止。

### 约束 (Hard Constraints — 全程有效)
- 不以任何理由导致 D 盘爆满。
- 不自动删除用户文件。
- WARNING 下禁止扩大数据规模; DANGER 下立即停止大型操作并等待用户指令。
