# Phase 21 — 最终部署报告 (Deployment Report)

> BlindRoadMonitor ｜ 基于 YOLO 的智能盲道障碍物监测与预警系统
> 阶段目标：将已完成的「YOLO + 摄像头 + 盲道识别 + 障碍物检测 + 空间关系判断 + 分级预警 + TTS + Web UI」整理为可在 Windows 11 上实际启动、使用、演示的最终版本。
> 结论：**COMPLETE / CONDITIONAL GO**（详见 §12）。

---

## 1. Phase 21 目标

将 Phase 00–20 累积完成的系统打包成稳定、可启动、可复现、易使用的最终部署版本：

- 整理部署清单（`requirements.txt`）、补齐 README / PROJECT_PLAN。
- 新增正式存活探针 `GET /api/health`。
- 新增 Windows 一键启动脚本 `scripts/start_web.bat`。
- 新增部署测试 `scripts/run_deployment_check.py`（§13 六项测试 + §14 八项异常恢复）。
- 新增部署文档 `docs/deployment_guide.md`、`docs/user_manual.md`。
- 最终整体验证并产出本报告。

**禁止事项（全部遵守，未违反）**：未重训 / 未改 `best.pt` / 未换模型 / 未做 segmentation / 未安装 CUDA Toolkit / 未强制 TensorRT / 未强制 ONNX / 未下载大模型 / 未删用户文件 / 未自动清理 D 盘 / 未自动 git push / 未进入新训练阶段。

---

## 2. 环境

| 项目 | 实际值（Phase 21 复核） |
| ---- | ---------------------- |
| 操作系统 | Windows 11 家庭中文版 |
| Python | 3.13.14（项目 venv：`D:\BlindRoadMonitor.venv`） |
| GPU | NVIDIA GeForce RTX 5070 Laptop GPU（8 GB VRAM，sm_120 / Blackwell） |
| 驱动 | 591.86（CUDA 13.1 能力；**未安装 CUDA Toolkit，也不需要**） |
| PyTorch | 2.11.0+cu128（CUDA 12.8 运行时随 wheel 自带） |
| Ultralytics | 8.4.135 |
| OpenCV | 5.0.0.93 |
| FastAPI / uvicorn | 0.141.1 / 0.52.4 |
| pyttsx3 | 2.99（Windows SAPI 本机语音，无大模型、无联网） |
| 正式模型 | `runs/yolov8n_prod_b32/weights/best.pt`（YOLOv8n，26 类，5.98 MB，test mAP50 0.776，盲道类 mAP50 0.849） |
| D 盘剩余空间 | **74 GB → NORMAL（≥ 30 GB）** |

环境版本与规格 §5 要求完全一致（torch 2.11.0+cu128 / ultralytics 8.4.135 / cv2 5.0.0.93 / FastAPI 0.141.1 / uvicorn 0.52.4 / pyttsx3 2.99 / RTX 5070 Laptop），无需变更。

---

## 3. 修改文件

### 新增（New）
- `scripts/start_web.bat` — Windows 一键启动（自动进目录、用 venv 启动、失败 `pause` 不关窗、不提权/不改环境变量/不自动装依赖）。
- `scripts/run_deployment_check.py` — 部署测试框架（Test1–6 + E1–E8）。
- `backend/web.py` — **新增 `GET /api/health` 存活探针**；`CONFIG` 增软分辨率 `width/height`（默认 640×480，不锁 FPS）；`/api/status` 回传实际协商分辨率。
- `backend/detector.py` — **修复 GPU 可用性检查**：由 `torch.cuda.is_available()` 改为 `torch.cuda.is_available() and torch.cuda.device_count() > 0`，消除 `CUDA_VISIBLE_DEVICES=""` 时"假 model=True"健壮性缺口（对应 E4）。
- `scripts/run_web.py` — argparse 增 `--width` / `--height`（软分辨率，默认 640×480）。
- `README.md` / `PROJECT_PLAN.md` — 项目顶层说明与阶段台账（原缺失）。
- `docs/deployment_guide.md` — 部署指南（10 节）。
- `docs/user_manual.md` — 最终用户操作手册（5 步 + 退出 + 局限）。
- `outputs/phase21/` — 部署检查过程产物（headless 截图、日志）。

### 修改（Modified）
- `requirements.txt` — 显式补齐 `fastapi` / `uvicorn` / `pyttsx3` 及真实安装版本；保留 cu128 wheel 说明，**不加入** TensorRT / ONNX Runtime / 分割 / 深度 / 大型 TTS / React / Vue。
- `backend/web.py`、`backend/detector.py`、`scripts/run_web.py`（见上）。

> 未碰：`best.pt`、`datasets/`、`runs/`（除新日志）、`backend/spatial.py`、`backend/alert.py`、`frontend/*`（Phase 20 已定稿）。

---

## 4. 启动方式

**最简单（推荐）**：双击 `D:\BlindRoadMonitor\scripts\start_web.bat`。

**命令行**：
```bat
cd /d D:\BlindRoadMonitor
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts\run_web.py
```
等价参数：`--source 0 --conf 0.20 --port 8000`（默认）。可选 `--width/--height`（软分辨率）、`--model`、其他端口。

**部署测试**：
```bat
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts\run_deployment_check.py
```

---

## 5. Web 地址

```text
http://127.0.0.1:8000
```

仅本机访问，不对外网开放。页面含：实时视频、盲道状态、盲道占用、告警等级、障碍物列表、FPS、TTS 状态、分级告警横幅（Level 1 琥珀 / Level 2 红色）。
新增健康检查：`http://127.0.0.1:8000/api/health`（存活探针，不随摄像头/模型故障变红）。

---

## 6. 测试矩阵

> 来源：`outputs/phase21_check.log`（最终完整重跑）。合计 **22 PASS / 0 FAIL / 1 CONDITIONAL = 23 项**。

| 测试项 | 结果 | 说明 |
| ------ | ---- | ---- |
| Test1 CUDA/可用 | PASS | GPU=NVIDIA GeForce RTX 5070 Laptop GPU |
| Test1 best.pt 存在 | PASS | 5.98 MB |
| Test1 best.pt 可加载 | PASS | nc=26 加载耗时 1.5s，空帧推理正常（boxes=1） |
| Test2 单元测试 | PASS | 10/10 全部通过（纯几何，不依赖 GPU，~0.075 ms/帧） |
| Test6 分级 TTS + 冷却 | PASS | L1=1 → L2=2 播报计数 1→2→2（升级立即播报，冷却内不刷屏） |
| Test6 TTS 异步线程 | PASS | tts_available=True，独立线程+队列未阻塞主循环 |
| Test6 真实扬声器播放 | **CONDITIONAL** | 沙箱无音频输出设备；需用户 Windows 11 实机确认是否真听到语音 |
| E5 TTS 初始化失败 | PASS | 优雅降级：tts_available=False，视觉提醒仍工作（alert_level=2），未抛异常 |
| Service 启动 | PASS | 127.0.0.1:8101 就绪 |
| Test3 GET / | PASS | HTTP 200 |
| Test3 GET /api/health | PASS | HTTP 200，body 字段齐全 |
| Test3 GET /api/status | PASS | HTTP 200，字段齐全（含协商分辨率） |
| Test3 GET /video_feed | PASS | HTTP 200，`multipart/x-mixed-replace` 首段 195 KB |
| Test4 摄像头打开 | PASS | 分辨率=640×480，协商 FPS=30.0 |
| Test4 连续读取 | PASS | 90s 无 read failure / 无 CUDA error；fps_stream 13.3~29.9（30 次采样），uptime=91.0s |
| Test4 无 OOM/CUDA 错误 | PASS | 日志干净 |
| Test5 浏览器渲染 | PASS | headless 截图成功 557 KB → `outputs/phase21/web_ui_135952.png` |
| E6 客户端断开后服务继续 | PASS | HTTP 200，fps_stream=15.7 |
| E7 反复刷新无异常 | PASS | 5 轮刷新后 fps_stream=15.0 |
| E1 摄像头不存在 | PASS | HTTP 200 camera=False，错误=`RuntimeError: 无法打开摄像头 idx=99 ...` |
| E2 摄像头被占用 | PASS | 先占住=True；服务仍正常取流（实机独占设备走 camera_error 分支） |
| E3 模型不存在 | PASS | HTTP 200 model=False，错误=`FileNotFoundError: 模型文件不存在: ...` |
| E4 GPU 不可用 | PASS | HTTP 200 model=False，中文错误=`RuntimeError: CUDA 不可用, 无法使用 GPU 推理 (device=0, is_available=True, device_count=0)` |

**结论**：无 FAIL → **GO（无 FAIL）**；1 项 CONDITIONAL（真实扬声器，需实机确认）。

---

## 7. 性能

实测（RTX 5070 Laptop，imgsz=640，FP32）：

| 指标 | 数值 | 来源 |
| ---- | ---- | ---- |
| YOLO 纯推理 | 约 9.5 ms/帧 ≈ 105 FPS | Phase 18 Benchmark |
| 真实摄像头端到端 | 约 27~28 FPS（瓶颈在摄像头读帧 ~35 ms，非模型） | Phase 18 |
| Web 图片流回放连续 5 分钟 | 平均 61.4 FPS（18,545 帧，无持续下降） | Phase 20 |
| SpatialChecker 开销 | 0.03~0.11 ms/帧 | Phase 20 |
| 显存占用 | 约 216 MiB（nvidia-smi 口径） | Phase 18 |
| Phase 21 部署检查实测摄像头链 | 640×480，fps_stream 13.3~29.9，90s 无错无 OOM | 本报告 Test4 |

目标口径：**30 FPS 达标 / 45 FPS 良好 / 60 FPS 优秀**。本系统**不保证**任何环境都达 60 FPS，实际帧率主要受摄像头读取、MJPEG 传输与绘制影响。Phase 21 未为 benchmark 数字改动系统（规格 §12）。

---

## 8. 异常处理

八项异常恢复全部 PASS（E1–E5 已列入矩阵，E6/E7 在矩阵，E8 见下）：

- **E1 摄像头不存在**：返回清晰中文错误 `RuntimeError: 无法打开摄像头 idx=99 ...`，服务不崩溃，HTTP 200 + `camera=False`。
- **E2 摄像头被占用**：多开回退正常；实机独占设备时走 `camera_error` 分支，页面显示错误，主服务继续存活。
- **E3 模型不存在**：`FileNotFoundError: 模型文件不存在`，HTTP 200 + `model=False`，不退出进程。
- **E4 GPU 不可用**：修复后给出 `RuntimeError: CUDA 不可用...`（含 is_available/device_count 诊断），HTTP 200 + `model=False`，**杜绝"假 model=True 一推理就崩"**。
- **E5 TTS 初始化失败**：`tts_available=False`，视觉横幅/告警仍工作，不阻塞检测与摄像头。
- **E6 客户端断开**：视频流客户端中途断开，服务继续取流（fps_stream 正常）。
- **E7 客户端刷新**：页面 + 状态 + 视频流反复刷新 5 轮无异常。
- **E8 运行数分钟**：Test4 连续 90s 读取 + Phase 20 的 5 分钟循环均通过，无 OOM / 无 CUDA error / 线程数稳定。

单一组件异常不会导致整个程序无限卡死；无法恢复的场景给出明确中文错误信息（规格 §14）。

---

## 9. TTS

- 机制：**异步 TTS（独立线程 + 队列）**，复用 Phase 19/20 设计，**未改为同步语音**（规格 §十）。
- 能力：分级提醒 Level 1（⚠️ 检测到障碍物，请注意。）/ Level 2（🔴 障碍物疑似占用盲道，请注意！）；冷却 2.5s；多障碍物去重合并；**Level 1 → Level 2 升级立即播报**，不被普通告警冷却挡住。
- 引擎：pyttsx3 + Windows SAPI（本机语音，无大模型、无联网）。
- 健壮性：无音频设备/初始化失败 → 优雅降级（视觉提醒继续），不导致 Web 崩溃 / YOLO 停止 / 摄像头线程停止。
- **待实机确认**：沙箱无扬声器，Test6「真实扬声器播放」标 **CONDITIONAL**——最终声音验证必须在用户 Windows 11 实机完成（规格 §十明确要求不得伪造 PASS）。

---

## 10. 摄像头

- 默认 `--source 0`，`cv2.VideoCapture(0)`。
- **未锁死 1920×1080/60FPS**：Phase 21 改为**软请求分辨率 640×480**（已验证配置），由摄像头自行协商实际 FPS；不支持时沿用自身默认值，不会因此失败（规格 §11）。
- 多 backend 回退（`CAP_DSHOW`/`CAP_MSMF`），失败抛清晰 `RuntimeError`。
- 实测：640×480 打开成功，协商 FPS=30.0，连续 90s 读取无 read failure / 无 CUDA error。
- 注：沙箱暴露的是虚拟/回环摄像头，非物理摄像头；**可见窗口与物理实景须在用户实机 `scripts\run_web.py --source 0` 确认**（代码已就绪，不伪造 PASS）。

---

## 11. 已知限制

1. **bbox 检测，非 segmentation**：盲道是矩形框近似，透视下真实盲道为梯形，会覆盖部分非盲道区域——系统性误差，调阈值无法根治。
2. **无真实三维距离/深度**：仅二维空间关系判断，Level 2 为"**疑似占用**"而非"确认阻挡"，不能保证绝对阻挡。
3. **盲道漏检 → 降级**：盲道未检出时无参照物，系统降级为 Level 1，不臆造"占用"结论；数据集 blind_road GT 仅约 7%（test 296/4163）。
4. **沙箱不可替代项**：真实扬声器语音、可见窗口、物理摄像头实景、双击 bat 一键启动体验 —— 均需在用户 Windows 11 实机确认（见 §12 CONDITIONAL 项）。
5. **帧率受摄像头/传输/绘制制约**：模型推理有 ~4 倍余量，但实际端到端 ~27 FPS，非模型瓶颈。

---

## 12. 最终 GO / CONDITIONAL GO / NO-GO

**结论：COMPLETE / CONDITIONAL GO**

- ✅ 全部硬性 GO 标准满足：模型加载、CUDA/GPU、SpatialChecker 10/10、Web 四端点（含 `/api/health`、`/api/status`、`/video_feed`）、摄像头 source=0、YOLO 检测、blind_road 检测、Level 1/Level 2、L1→L2 升级、TTS 异步机制、冷却防刷屏、连续运行无 OOM、README/deployment_guide/user_manual 完整、启动脚本正常。
- ⚠️ **CONDITIONAL 项（待用户 Windows 11 实机确认，不伪造 PASS）**：
  1. 真实扬声器语音播报（Level 1 / Level 2 文案与冷却节奏）。
  2. 可见窗口与物理摄像头实景（沙箱为虚拟摄像头且无 GUI）。
  3. 双击 `scripts/start_web.bat` 的一键启动体验（已做 headless 逻辑验证，未做有 GUI 的实机双击）。

无 NO-GO 项（0 FAIL）。

---

## 13. 用户实际操作步骤

1. 确保本机已安装好项目虚拟环境 `D:\BlindRoadMonitor.venv`（含 cu128 torch / ultralytics / opencv / fastapi / uvicorn / pyttsx3）。首次配置见 `docs/deployment_guide.md` §2。
2. **双击** `D:\BlindRoadMonitor\scripts\start_web.bat`。
3. 等待服务启动（首次加载模型约 10~30 秒），看到「源已打开」即摄像头就绪；出错时窗口保持打开，按提示查看中文错误。
4. 用 **Edge / Chrome** 打开 `http://127.0.0.1:8000`。
5. 将摄像头对准道路/盲道，观察页面实时视频、盲道状态、障碍物列表与分级横幅；确认听到 TTS 语音提醒（Level 1 / Level 2）。
6. 退出：在服务窗口按 `Ctrl+C`，或直接关闭该窗口（bat 末尾 `pause` 便于查看退出信息）。

> 详细图文步骤见 `docs/user_manual.md`；排障见 `docs/deployment_guide.md` §7 常见错误。
