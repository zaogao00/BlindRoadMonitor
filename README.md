# 基于 YOLO 的智能盲道障碍物监测与预警系统

> BlindRoadMonitor ｜ 当前阶段：**Phase 21 — 最终打包与部署（COMPLETE / CONDITIONAL GO）**

## 1. 项目简介

基于 YOLO 的智能盲道障碍物监测与预警系统，通过摄像头实时识别盲道和障碍物，并基于二维空间关系判断障碍物是否**疑似**占用盲道，同时通过 Web UI 和 TTS 语音提醒用户。

完整链路：

```text
摄像头 → YOLOv8n 检测 → 盲道识别 + 障碍物识别
       → 空间关系判断（IoU / 中心点 / 交叠比）
       → 分级预警（Level 0/1/2）→ 网页红色/琥珀横幅 + TTS 语音
```

正式模型：`runs/yolov8n_prod_b32/weights/best.pt`（YOLOv8n，26 类，test mAP50 0.776，盲道类 mAP50 0.849）。

## 2. 环境

| 项目 | 实际值（Phase 21 复核） |
| ---- | ---------------------- |
| 操作系统 | Windows 11 家庭中文版 |
| Python | 3.13.14（项目 venv：`D:\BlindRoadMonitor.venv`） |
| GPU | NVIDIA GeForce RTX 5070 Laptop GPU（8 GB VRAM，sm_120） |
| 驱动 | 591.86（CUDA 13.1 能力；**未安装 CUDA Toolkit，也不需要**） |
| PyTorch | 2.11.0+cu128（CUDA 12.8 运行时随 wheel 自带） |
| Ultralytics | 8.4.135 |
| OpenCV | 5.0.0.93 |
| FastAPI / uvicorn | 0.141.1 / 0.52.4 |
| pyttsx3 | 2.99（Windows SAPI 本机语音，无大模型） |

## 3. 安装

> 如果你已经在本机跑通过本项目，**不要重装**，直接跳到第 4 节。

```bat
cd /d D:\BlindRoadMonitor

:: 1) 创建隔离虚拟环境
C:\Users\<你>\.workbuddy\binaries\python\versions\3.13.12\python.exe -m venv D:\BlindRoadMonitor.venv

:: 2) 安装 PyTorch CUDA wheel（必须走 PyTorch 官方索引，不能用默认 PyPI）
D:\BlindRoadMonitor.venv\Scripts\python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

:: 3) 安装其余依赖
D:\BlindRoadMonitor.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**关于 PyTorch**：本项目使用**已经验证过的 CUDA-enabled wheel（cu128）**，**不要求额外安装 CUDA Toolkit**，也不需要 TensorRT / ONNX Runtime。请不要为了"看起来更专业"更换 CUDA/PyTorch 安装方案。

模型权重 `runs/yolov8n_prod_b32/weights/best.pt`（5.98 MB）已随仓库提供，无需下载。

## 4. 启动

**方式 A — 电脑摄像头（推荐）**：双击

```text
D:\BlindRoadMonitor\scripts\start_web.bat
```

**方式 B — 手机摄像头（IP Webcam）**：手机开 IP Webcam 并点"启动服务器"（与电脑同一 WiFi），然后双击

```text
D:\BlindRoadMonitor\scripts\start_web_phone.bat
```

该脚本会自动连接手机流、启动服务，约 12 秒后自动打开浏览器直达画面；若手机 IP 变化，用记事本改脚本顶部的 `SOURCE` 一行即可。两个脚本出错时窗口都会保持打开，方便查看中文错误信息。

**命令行方式**：

```bat
cd /d D:\BlindRoadMonitor
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts\run_web.py
```

首次启动需要加载模型（约 3~10 秒，GPU 预热后更快）；看到 `[web][worker] 源已打开` 即表示摄像头已就绪。

停止服务：在服务窗口按 `Ctrl+C`，或直接关闭该窗口。

## 5. 浏览器

```text
http://127.0.0.1:8000
```

用 Edge 或 Chrome 打开即可（仅本机访问，不对外网开放）。页面包含：实时视频、盲道状态、盲道占用、告警等级、障碍物列表、FPS、TTS 状态、分级告警横幅。

## 6. 参数

```bat
python scripts\run_web.py --source 0 --conf 0.20 --port 8000
```

| 参数 | 默认 | 说明 |
| ---- | ---- | ---- |
| `--source` | `0` | 摄像头索引；也可填图片/视频路径做回放验证，或填 `http://…/video`、`rtsp://…` 网络视频流（如手机 IP Webcam） |
| `--conf` | `0.20` | 置信度阈值。已验证配置；可调 0.15~0.25（调低召回高但误报多） |
| `--port` | `8000` | HTTP 端口（被占用时换 8010、8080 等） |
| `--width` / `--height` | `640` / `480` | **软设置**请求分辨率，摄像头不支持则沿用自身协商值；**不锁 FPS** |
| `--model` | `runs\yolov8n_prod_b32\weights\best.pt` | 模型权重路径 |

## 7. 告警等级

| Level | 状态 | 含义 | 页面 / 语音 |
| ----- | ---- | ---- | ----------- |
| 0 | `NONE` | 未检测到障碍物 | 无告警 |
| 1 | `NORMAL_OBSTACLE` | 有障碍物，但无足够证据认为占用盲道 | ⚠️ 检测到行人，请注意。 |
| 2 | `BLOCKING_SUSPECTED` | 空间关系满足疑似占用条件 | 🔴 障碍物疑似占用盲道，请注意！ |

- **Level 2 覆盖 Level 1**：同时存在多个障碍物时，只要有一个疑似占用盲道，就优先显示 Level 2。
- **语音冷却 2.5 秒**，且 Level 1 → Level 2 升级会**立即**触发一次高级告警，不会被普通告警的冷却挡住。
- 疑似占用的判定规则：`IoU ≥ 0.10` **或**（障碍物中心在盲道框内且交叠 ≥ 0.05）**或**（障碍物落入盲道的比例 ≥ 0.20）。

## 8. 技术限制

- 当前是 **bounding box 目标检测**，**不是 segmentation**，没有盲道的像素级区域。
- **没有真实的三维距离/深度信息**，未使用深度摄像头。
- Level 2 的含义是"**疑似占用**盲道"，**不是"确认阻挡"**，不能保证绝对阻挡。
- 透视下盲道实际为梯形，其 bbox 是矩形近似，会覆盖部分非盲道区域 —— 这是**表示形式带来的系统性误差**，调阈值无法根治。
- **盲道漏检时系统会降级为 Level 1**（没有参照物就不做占用判断），不会臆造"占用"结论。
- 数据集本身 blind_road 标注稀疏（test 集 4163 张中仅 296 张含盲道标注，约 7%）。

## 9. 性能

实测数据（RTX 5070 Laptop，imgsz=640，FP32）：

| 指标 | 数值 | 来源 |
| ---- | ---- | ---- |
| YOLO 纯推理 | 约 9.5 ms/帧 ≈ 105 FPS | Phase 18 Benchmark |
| 真实摄像头端到端 | 约 27~28 FPS（瓶颈在摄像头读帧） | Phase 18 |
| Web 图片流回放 | 平均 61.4 FPS（5 分钟连续，18,545 帧） | Phase 20 |
| SpatialChecker 开销 | 0.03~0.11 ms/帧 | Phase 20 |
| 显存占用 | 约 216 MiB（nvidia-smi 口径） | Phase 18 |

目标口径：**30 FPS 达标 / 45 FPS 良好 / 60 FPS 优秀**。本系统**不保证**任何环境下都达到 60 FPS —— 实际帧率主要受摄像头读取、MJPEG 传输与绘制影响。

## 目录结构

```text
D:\BlindRoadMonitor
├── backend/     检测器 / 摄像头 / 提醒 / 空间关系 / FastAPI 应用
├── frontend/    index.html + style.css + app.js（原生，无构建）
├── scripts/     启动脚本、验证脚本、一键启动 bat
├── tests/       单元测试（test_spatial.py 纯几何，不依赖 GPU）
├── docs/        各阶段报告 + 部署指南 + 用户手册
├── runs/        训练与模型权重（best.pt）
├── datasets/    数据集（只读）
└── outputs/     验证过程产物（样本图、截图、日志）
```

## 文档索引

- `docs/deployment_guide.md` — 部署指南（环境/安装/启动/排错）
- `docs/user_manual.md` — 最终用户操作说明（不懂 Python 也能用）
- `docs/phase21_deployment_report.md` — Phase 21 部署报告与测试矩阵
- `docs/spatial_relation_report.md` — Phase 20 空间关系判断报告
- `docs/web_ui_report.md` — Phase 19 Web UI 报告
- `docs/deployment_optimization_report.md` — Phase 18 性能优化报告
- `PROJECT_STATUS.md` / `CHANGELOG.md` / `PROJECT_PLAN.md` — 项目状态与变更记录
