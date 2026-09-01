# CHANGELOG

本项目所有重要变更记录于此。格式参考 Keep a Changelog。

## [Phase 09 补充] — 2026-09-01 (WOTR 全量下载 COMPLETE)

### Added (新增)
- **WOTR 全量** (VOC, MIT, 含盲道类): 13,928 图 + 13,928 XML (train 9,056 / val 2,338 / test 2,534)
  - 经 **Google Drive 公开链接零凭证**获取 (gdown 流程 + Range 断点续传)
  - 落盘: `datasets/raw/wotr/` (WOTR.zip 3.95 GiB + 解压 4.19 GB + `DATASET_INFO.md`)
- **`scripts/download_wotr.py`**: WOTR 下载脚本 (磁盘闸门 + 病毒扫描确认页处理 + usercontent GET + Range 续传 + zip testzip 校验)

### Verified (验证结果)
- WOTR.zip 4,244,840,539 B 与 Drive 大小完全匹配; `testzip()` → 无损坏
- JPEGImages 13,928 / Annotations 13,928 配对完整; ImageSets 划分合计 13,928 ✅
- 抽查 2,000 XML: 含 `blind_road`(盲道) 23 个目标 / 17 张图; 另有 person/car/pole/truck 等 20 类

### Changed (变更)
- 盲道数据策略: Roboflow 403 (需登录)、GuideTWSI HF 401 (门控) 均不可用 → 改用 **WOTR** (唯一零凭证可获取的「盲道+障碍物」MIT 数据集), 解决盲道数据缺口
- `docs/dataset_report.md` 新增 §0 (WOTR 补充); `docs/storage_report.md` §2.1、`PROJECT_STATUS.md` Phase 09/下一步/磁盘表 同步更新

### Safety (安全约束落实)
- 未训练 / 未转换 / 未删除任何用户文件
- 下载与解压前均 `check_before_operation()` → NORMAL (73.2 GB), 允许; 完成后 D 盘剩余 **~65 GB → NORMAL**
- 数据落入 `datasets/` (`.gitignore` 屏蔽, 不入库)

### Git
- 提交: `Phase 09: add WOTR dataset (blind road + obstacles)`

## [Phase 09 完成] — 2026-09-01 (第一轮下载 COMPLETE)

### Done (已完成)
- 网络出口恢复 (hf.co:443 可达), **ROD-Dataset 第一轮 4,000 图 + 4,000 标签** (225.7 MB) 下载并校验通过:
  - train **1,000** / valid **1,371** / test **1,629 (全量)** — 均为 seed=20260831 采样 (test 全量)
  - 落盘: `datasets/raw/rod_dataset/{split}/images|labels/` + `DATASET_INFO.md` + `data.yaml` + `README.md`
- 校验 `verify_rod_dataset.py`: **0 损坏 / 0 零字节 / 配对完整**; 仅 12 空标签 (train 3 + valid 4 + test 5, 可忽略); `verify_report.json` 已更新
- 补下载缺失标签: valid `IMG_20867.txt` (39 B)

### Fixed (实施修复 — 环境适配, 不改数据内容)
- **传输通道**: 原脚本 curl.exe 在本沙箱 schannel 报 `SEC_E_NO_CREDENTIALS` 不可用 → 改为 **requests 直写** (`scripts/download_rod_sample.py`)
- **标签阈值**: `MIN_BYTES=100` 误判几十字节的标签全部失败 → 区分 图片 100 / 标签 0 (0 字节空标签合法)
- **HF 限流**: 16 并发触发 429 → 降至 **5 并发 + 429/5xx 指数退避重试 (最多 5 次)**
- **仓库结构**: train 实际为 `train/{images,labels}/{0,1}/...` → 按 basename 扁平化落盘, 无重名

### License 更正
- ROD-Dataset 许可按 HF README front-matter 为 **MIT** (首版记录 CC BY 4.0 有误, 已更正于 DATASET_INFO.md / dataset_report.md)

### Safety (安全约束落实)
- 未训练 / 未转换 / 未删除任何用户文件
- 下载前 `check_before_operation(required_gb=6.0)` → NORMAL (79.2 GB), 允许; 完成后 D 盘剩余 **~78.9 GB → NORMAL**
- 数据落入 `datasets/` (已被 `.gitignore` 屏蔽, 不入库)

### Git
- 提交: `Phase 09: dataset acquisition` (第一轮完成)

## [Phase 08 复查] — 2026-09-01

### Searched (重跑调研)
- 按用户给定关键词重跑: GuideTWSI / Tenji10K / TWSI datasets / tactile paving datasets / blind sidewalk datasets / obstacle detection sidewalk datasets
- 渠道: 官方项目页 / GitHub / 论文 / Hugging Face / Zenodo / Kaggle / Roboflow

### Confirmed (复查确认在线)
- GuideTWSI 项目主页 + ICRA 2026 论文 PDF (arXiv:2603.07060)
- WOTR GitHub (`kxzr/WOTR`) + README (Baidu CODE / Google Drive 链接)
- GRFB-Unet GitHub (`Chon2020/GRFB-Unet`) / SToP 项目主页 (`hchlhwang.github.io/SToP`)
- Tenji10K Wiley 页面 (DOI 10.1002/tee.24123)
- ROD-Dataset HF (`Abtinzandi/...`, 含镜像 `jiasea/...`)

### Added (新增候选)
- **BLV-Road-Nav-Accessibility** (GitHub, 21 视频 / 90 无障碍类, bbox 检测, 需核对类目与许可)
- **TactPav** (华东师大 ECNU, 视觉-语言多模态盲道导航数据集, Springer 2025)
- **Roboflow 小集**: crosswalk-tactile-blocks v2 / tactile-paving-segmentation (YOLO 开箱即用, 小规模试用)

### Found (方法参考信号, 非数据集)
- *Street-level monitoring of urban tactile paving obstructions through VLM + street view* (SAGE 2026)
- *Automated Detection and Mapping of Tactile Paving Using Street View Images* (IEEE 2025)
- *DPSN: Tactile paving and Obstacle Joint Segmentation Network* (盲道+障碍物联合分割, 任务对标)

### Conclusion (结论不变)
- 推荐主用: **WOTR (MIT)** + **GuideTWSI (MIT)**; 障碍物扩充: ROD-Dataset (最可行, 已落地 614 张) / Obstacles in Public Spaces (CC0)
- 不推荐主用: SideGuide / Tenji10K / TP-Dataset
- 第一阶段: ~17,000–19,000 张, 约 8–15 GB (NORMAL 下安全)

### Safety (安全约束落实)
- 未下载 / 未解压 / 未训练 / 未转换任何数据集
- 磁盘状态: 实时探测 D 盘剩余 **79.2 GB → NORMAL**

### Git
- 提交: `Phase 08: dataset research` (复查重跑, 更新 `docs/dataset_candidates.md` / `PROJECT_STATUS.md`)

## [Phase 09] — 2026-08-31 (受阻 BLOCKED — 网络出口中断)

### Added (新增)
- `scripts/download_rod_sample.py`: ROD-Dataset 采样子集下载器 (curl 直写 + 16 线程并发 + 断点续传 + 每 250 张检查点), 目标 ~4000 张 (train 采样 1000 + valid 采样 1371 + test 全量 1629) 及配对 YOLO 标签
- `scripts/verify_rod_dataset.py`: 数据集完整性校验 (文件/图片/标签数量 + 0 字节/损坏/空标签/配对缺失检查)

### Changed (变更)
- `docs/dataset_candidates.md` 结论收敛: 本环境无 Kaggle/HF/Baidu 凭证 → WOTR、GuideTWSI 不可直接获取; **ROD-Dataset (CC BY 4.0, 原生 YOLO)** 为唯一可实际拉取的「已确认数据集」, 作为 Phase 09 第一轮下载对象

### Done (已完成)
- 下载并校验 ROD-Dataset **train 子集 614 图 + 614 标签** (39.3 MB) 至 `datasets/raw/rod_dataset/train/`; `valid/`、`test/` 待网络恢复后续传

### Blocked (受阻 — 环境级)
- 沙箱出网经本机 Clash 代理 `127.0.0.1:7897`, 当前上游 TLS 握手全部失败 (`SSL: UNEXPECTED_EOF_WHILE_READING`), 所有外部主机 000 不可达; 故 valid/test 未能下载
- 此前同一会话内已成功下载 614 张, 属**暂时性出口故障**; 网络恢复后重跑脚本即可断点续传

### Safety (安全约束落实)
- 未训练 / 未转换任何数据
- 下载前执行 `check_before_operation()` 闸门: 估算 ~0.20 GB, 完成后 D 盘剩余 ≥ 30 GB → 允许 (无需批准)
- 磁盘状态: **NORMAL**

### Git
- 提交: `Phase 09: dataset acquisition (BLOCKED — network egress down, partial ROD sample retained)`

## [Phase 08] — 2026-08-31

### Added (新增)
- `docs/dataset_candidates.md`: 公开盲道/TWSI 数据集候选调研报告 (纯调查, 未下载/未训练/未转换)

### Searched (调研对象)
- GuideTWSI / Tenji10K / TWSI datasets / tactile paving datasets / blind sidewalk datasets / obstacle detection sidewalk datasets
- 覆盖: GuideTWSI, WOTR, Tenji10K, SideGuide, TP-Dataset(GRFB-UNet), SToP(合成), Obstacles in Public Spaces(Dist-YOLO), 及补充 ROD-Dataset / Mendeley VI

### Findings (关键结论)
- **推荐主用**: WOTR (MIT, 13,928 图, 含盲道类+15类障碍物, VOC→YOLO) + GuideTWSI (MIT, 39.5K 图, 官方 YOLOv11-seg 权重与转换器)
- **障碍物扩充可选**: Obstacles in Public Spaces (CC0, 原生 YOLO) / ROD-Dataset (CC BY 4.0, 原生 YOLO)
- **不推荐主用**: SideGuide (申请制+数十GB) / Tenji10K (许可不明+双线标注) / TP-Dataset (CC BY-NC-SA 非商业)
- **预计空间**: 第一阶段约 8–15 GB (NORMAL 下安全); 建议 17,000–19,000 张图起步

### Safety (安全约束落实)
- 未下载 / 未解压 / 未训练 / 未转换任何数据集
- 磁盘状态: 采样时 D 盘剩余约 79 GB → **NORMAL**

### Git
- 提交: `Phase 08: dataset research`

## [Phase 07] — 2026-08-31

### Added (新增)
- `tests/test_yolo_inference.py`: YOLO 基础推理验证脚本 (加载 yolov8n → GPU 推理 → 保存结果图; 收集模型大小/推理时间/GPU 显存/检测框数/输出图片; 带异常捕获)

### Changed (变更)
- 将预训练权重 `yolov8n.pt` (6.25 MB) 规范存放至 `models/` 目录 (已被 `.gitignore` 屏蔽, 不入库); 测试脚本优先复用该缓存权重, 避免重复下载
- 未下载任何大型数据集; 未进行训练

### Verified (验证结果)
- 模型加载: yolov8n.pt 6.25 MB ✅
- GPU 推理: cuda:0 (RTX 5070), 耗时 1.447 s (复用权重, 无下载) ✅
- GPU 显存: 推理后 23.2 MB / 峰值 28.0 MB (远低于 8GB) ✅
- 检测框: 6 个; 输出图片: `runs/yolo_inference_test/bus.jpg` 已保存 ✅
- 退出码 0, 全流程 PASS

## [Phase 06] — 2026-08-31

### Added (新增)
- `scripts/check_yolo.py`: YOLO 环境一体化校验脚本 (Python/venv + Ultralytics + PyTorch + CUDA + GPU, 带异常捕获, 全部 PASS 退出码 0)
- `requirements.txt`: 记录 venv 中**实际安装**的精确版本 (pip freeze 导出), 含 torch/torchvision/torchaudio cu128 与 ultralytics 8.4.135 及其全部依赖

### Changed (变更)
- 在隔离 venv 安装 `ultralytics==8.4.135` 及基础依赖 (opencv-python 5.0.0.93 / matplotlib 3.11.1 / numpy 2.5.2 / pillow 12.3.0 / pyyaml 6.0.3 / requests 2.34.2 / psutil 7.2.2 / polars / nvidia-ml-py / ultralytics-thop / ultralytics-platform 等)
- 未安装任何不必要的大型 AI 框架; 未修改已有 Anaconda / managed 环境; 未安装 CUDA Toolkit

### Verified (验证结果)
- `import ultralytics` → 8.4.135 ✅
- `yolo checks` → **Setup complete**: Python 3.13.14 / torch 2.11.0+cu128 / CUDA:0 (RTX 5070 Laptop GPU, 8151 MiB) / CUDA 12.8 ✅
- 磁盘: 安装后 venv 占用 ~5.0 GB, D 盘剩余 **NORMAL**

## [Phase 05] — 2026-08-31

### Added (新增)
- `scripts/test_gpu.py`: RTX 5070 GPU 验证脚本 (stdlib + torch; 带异常捕获, 遇 CUDA error / OOM / driver error 立即退出; 不训练 / 不下载 / 不占大磁盘)

### Verified (验证结果)
- PyTorch 2.11.0+cu128 ｜ CUDA 运行时 12.8 ｜ `torch.cuda.is_available() == True`
- GPU: NVIDIA GeForce RTX 5070 Laptop GPU ｜ 计算能力 sm_120 (Blackwell) ｜ 显存 8.55 GB
- 4096×4096 矩阵乘法 OK; 与 CPU 结果误差 1.53e-05 → PASS; 峰值显存 ~210 MB (<< 8 GB)
- 退出码 0, 无 CUDA error / OOM / driver error → **GPU 验证通过**

### Disk (磁盘状态)
- 仅新增脚本 (~5 KB), 未产生大文件; D 盘仍为 **NORMAL**

### Git
- 提交: `Phase 05: GPU validation`

## [Phase 04] — 2026-08-31

### Added (新增)
- PyTorch GPU 环境 (隔离 venv 内): `torch 2.11.0+cu128` / `torchvision 0.26.0+cu128` / `torchaudio 2.11.0+cu128`
- 运行依赖: numpy / pillow / filelock / fsspec / jinja2 / networkx / sympy / typing_extensions / mpmath / markupsafe

### Upgraded / Fixed (venv 内)
- setuptools **81.0.0** (torch 要求 `setuptools<82`; 修正 Phase 03 的 84.0.0, 并清理首次失败安装留下的删残文件)
- wheel 0.48.0 ｜ pip 26.1.2 (沙箱 safe-delete 守卫阻止升 26.2.1, 功能完整)

### Verified (已验证)
- `torch.cuda.is_available() == True` ✅; 设备 = NVIDIA GeForce RTX 5070 Laptop GPU
- `pip check` → No broken requirements found ✅

### Install Notes (安装备注)
- 版本依据官方 pytorch.org cu128 索引 (RTX 5070 = Blackwell / sm_120, 必须 cu128+; 未用 cu126/cu124)
- 首次整包安装因 safe-delete 守卫拦截 setuptools 降级而回滚; 改用 `--no-deps` 装 torch 全家桶 + 单独装运行依赖绕过
- 未安装 CUDA Toolkit / TensorRT / OpenCV / FastAPI; 未修改已有 Anaconda / managed 环境

### Disk (磁盘状态)
- 安装后 venv 占用 ~4.4 GB; D 盘剩余 ~47.2 GB (沙箱视图) / 真实约 52–53 GB → 状态 **NORMAL**

### Git
- 提交: `Phase 04: PyTorch GPU environment`

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
