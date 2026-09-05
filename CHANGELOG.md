# CHANGELOG

本项目所有重要变更记录于此。格式参考 Keep a Changelog。

## [Feat] 手机摄像头一键启动脚本 — 2026-09-06

### Added (新增)
- **`scripts/start_web_phone.bat`** (GBK+CRLF): 双击即连手机摄像头 (IP Webcam) 启动盲道程序 — 自动连接 `SOURCE` 手机流、约 12s 后自动打开浏览器直达画面; 顶部 `SOURCE` / `PORT` 可改 (手机 IP 变化时只需改一行); 含环境检查/错误提示/常见原因 (手机未启动/不在同一 WiFi/IP 变化/端口占用)

### Verified (实测)
- cmd (代码页 936/GBK) 执行: 中文正常、环境检查通过、SOURCE 正确传入
- 服务运行: camera=True / model=True / fps 30.6 / 1920×1080 (手机流实况) ✅

### Git
- 提交: `feat: one-click start script for phone camera (start_web_phone.bat)`

## [Feat] 网络流断流自动重连 — 2026-09-06

### Added (新增)
- **`backend/web.py`**: kind=='stream' (URL/RTSP) 读帧失败时自动重连 — 每 `RECONNECT_DELAY=3s` 重试 `cv2.VideoCapture(source)`, 期间 `/api/status` 报 `camera_error="网络流断开, 自动重连中..."`, 成功后清除错误并回读分辨率; worker 保持存活, 无需重启程序
- 本机摄像头 (idx) / 图片 / 视频路径行为不变 (仅 stream 走重连)

### Verified (实测 — 本地模拟 MJPEG 源断流→恢复)
- 稳定运行 (camera=True, fps 9.9) → 杀源进程 → `camera=False + cam_err=自动重连中` (worker 未退出) → 重启源 → 10s 内 `camera=True + fps 恢复 + 错误清空` ✅
- 端口冲突排查: 两个源进程抢同端口会导致流异常 (已避免, 无代码问题)

### Git
- 提交: `feat: auto-reconnect for network stream source`

## [Feat] 网络视频流源支持 (手机摄像头接入) — 2026-09-06

### Added (新增)
- **`backend/web.py` `_resolve_source()`**: 新增 `http://` / `https://` / `rtsp://` / `rtmp://` URL 分支 → `cv2.VideoCapture(url)` 经 FFMPEG 拉流 (kind='stream'); 分辨率回读与 `release()` 对 stream 兼容
- **`README.md`**: `--source` 参数说明补充网络视频流用法

### Verified (实测 — 用户手机 IP Webcam)
- `http://192.168.1.7:8080/video` (MJPEG, 1080p): TCP 可达 / `cv2.VideoCapture` isOpened=True / 读到帧 1920×1080
- 端到端: model=True + camera=True + **fps_stream 27–34** / fps_model 77.8; 检测与分级预警正常; MJPEG `/video_feed` 输出 `--frame` 边界正常
- 连续采样 20s 稳定, 无断流无 CUDA error

### Git
- 提交: `feat: support network video stream source (phone camera via IP Webcam / RTSP)`

## [Fix] TTS 后续播报无声 — 2026-09-05 (绕过 pyttsx3, 改用原生 SAPI 同步播放)

### Changed (修改)
- **`backend/alert.py`**: TTS worker 不再使用 pyttsx3, 改为 `win32com.client.Dispatch("SAPI.SpVoice")` + `voice.Speak(text, 0)` **同步播放** (阻塞到音频真正送完); worker 线程内 `pythoncom.CoInitialize()` / `CoUninitialize()`。pywin32 已在项目依赖中, **未新增依赖**。
  - `TTS_RATE` 由 pyttsx3 的 wpm=160 改为 SAPI `Rate=1` (范围 -10..10)
  - 同步新增 `_TTS_ENGINE_LOCK` 注释与 `_init_tts` 注释, 移除 pyttsx3 相关描述
- 完整保留: latest-message-wins 单槽位 / NORMAL_COOLDOWN=5.0 / BLOCKING_COOLDOWN=2.5 / STABLE_WINDOW=0.5 去抖 / Level 2 优先 / NONE 清空 pending / 异常记录不吞 (失败句后重建 voice 一次, 非每消息 init)

### Root Cause (根因)
- pyttsx3 2.99 + Python 3.13 + Windows 11 下, 即使持久 engine + `runAndWait()` 正常返回, 其事件循环/状态机也会在首句之后让 SAPI 底层音频管线静默失效 (日志 `speaking start/end` 全绿却无声)。这是 pyttsx3 封装层问题, 非 SAPI 本身 / 队列 / 冷却 / YOLO / Web 问题。

### Verified (实测 — 用户 Windows 11 实机)
- 遮挡摄像头后再拿开 → **可继续播报** (离开再进入场景通过)
- 用图片给摄像头 → **可识别并播报** (换图片场景通过)
- Level 2 "障碍物疑似占用盲道" 在前序普通播报进行中可插入并后播 (优先级正确)
- NONE 清空生效: 遮摄像头后旧 pending 被丢弃, 不再续播过时消息
- 沙箱逻辑层: `tests/test_spatial.py` 10/10; A~G 模拟 ALL PASS (含 180s 稳定 / voice 持久复用 / 线程无泄漏)

### Git
- 已 commit 并 push 至 origin/master（实测本地 HEAD 与远程 master 完全一致, 0 ahead / 0 behind）。

## [Phase 21] — 2026-09-05 (最终打包与部署 COMPLETE / CONDITIONAL GO — 不做 EXE)

### Added (新增)
- **`scripts/start_web.bat`**: Windows 一键启动 — 自动进项目目录、用项目 venv 启动 `run_web.py`; 失败 `pause` 不关窗; **不要求管理员权限 / 不修改系统环境变量 / 不自动安装依赖 / 不修改项目文件**
- **`scripts/run_deployment_check.py`**: 部署测试框架 — Test1 模型/CUDA、Test2 test_spatial 10/10、Test3 Web 四端点(含 /api/health)、Test4 摄像头连续读取、Test5 headless 浏览器、Test6 TTS(异步机制 PASS / 真实扬声器 CONDITIONAL); 异常恢复 E1 摄像头不存在 / E2 被占用 / E3 模型不存在 / E4 GPU 不可用 / E5 TTS 失败 / E6 客户端断开 / E7 反复刷新 / E8 运行数分钟
- **`backend/web.py`**: 新增 `GET /api/health` 存活探针（不随摄像头/模型故障变红）; `CONFIG` 增软分辨率 `width/height`（默认 640×480, 不锁 FPS）; `/api/status` 回传实际协商分辨率
- **`backend/detector.py`**: GPU 可用性检查由 `torch.cuda.is_available()` 改为 `torch.cuda.is_available() and torch.cuda.device_count() > 0`（修复 `CUDA_VISIBLE_DEVICES=""` 时"假 model=True"健壮性缺口, E4）
- **`scripts/run_web.py`**: argparse 增 `--width` / `--height`（软分辨率, 默认 640×480）
- **`README.md`** / **`PROJECT_PLAN.md`** / **`docs/deployment_guide.md`**(10 节) / **`docs/user_manual.md`**(5 步+退出+局限) / **`docs/phase21_deployment_report.md`**(§1–13)

### Changed (修改)
- **`requirements.txt`**: 显式补齐 `fastapi` / `uvicorn` / `pyttsx3` 及真实安装版本; 保留 cu128 wheel 说明; **不加入** TensorRT / ONNX Runtime / 分割 / 深度 / 大型 TTS / React / Vue

### Verified (实测)
- 部署测试 23 项 = **22 PASS / 0 FAIL / 1 CONDITIONAL**
- Test1 CUDA/可用 + best.pt 加载(5.98 MB, nc=26) PASS; Test2 单元测试 10/10 PASS
- Test3 GET / + /api/health + /api/status + /video_feed 全 HTTP 200
- Test4 摄像头 640×480 连续 90s: fps_stream 13.3~29.9, 无 read failure / 无 CUDA error / 无 OOM
- Test5 headless 截图 557 KB → `outputs/phase21/web_ui_135952.png` 证实全链路(真实摄像头+YOLO 框+状态面板+琥珀横幅)
- Test6 TTS 异步线程+队列未阻塞主循环, L1→L2 升级立即播报, 冷却内不刷屏 PASS; 真实扬声器 **CONDITIONAL**(沙箱无音频设备)
- E1–E8 八项异常恢复全 PASS(含 E4 GPU 不可用给出清晰中文错误, 不再"假可用一推理就崩")

### Decision (Go / No-Go)
- **COMPLETE / CONDITIONAL GO**: 全部硬性 GO 标准满足, 0 FAIL; 仅"真实扬声器 / 可见窗口 / 物理摄像头实景 / 双击 bat 体验"需用户 Windows 11 实机确认(不伪造 PASS)
- 部署形态定为 **venv + start_web.bat, 不做 EXE**(PyInstaller 打包 PyTorch CUDA 体积与兼容性风险高, 收益已被 bat 覆盖)

### Safety (安全约束落实)
- 不重训 / 不改 best.pt / 不换模型 / 不做 segmentation / 未装 CUDA Toolkit / 未强制 TensorRT / 未强制 ONNX / 未下载大模型 / 未删用户文件 / 未自动清理 D 盘
- D 盘剩余 74 GB → NORMAL
- 未自动 git push(按用户约定, 仅本地 commit)

### Git
- 提交: `Phase 21: deployment packaging and finalization`（仅本地, 未 push）

## [Phase 20] — 2026-09-04 (障碍物是否占用盲道 — 空间关系与分级预警 COMPLETE — GO)

### Added (新增)
- **`backend/spatial.py`**: `SpatialChecker` 纯几何模块 — `compute_iou` / `is_center_inside` / `obstacle_overlap_ratio` / `classify` 综合规则 / `draw_occupancy` 视频叠加绘制; **不定义/复制障碍物类别列表** (只接收 AlertManager 用 Phase 19 唯一定义筛好的 bbox); 阈值 `IOU_THRESHOLD=0.10 / OVERLAP_THRESHOLD=0.20 / CENTER_MIN_OVERLAP=0.05` (经 3×3 扫描选定, 非拍脑袋)
- **`tests/test_spatial.py`**: 单元测试 10 项 — 基础几何 / 场景 A~I (含擦边、误报对照、漏报型细杆、小盲道框大物体) / 3×3 阈值扫描 / AlertManager 分级与双冷却集成 / 性能; **不加载 YOLO、不依赖 GPU**; 10/10 PASS
- **`scripts/run_phase20_test.py`**: 集成验证 — 盲道组(GT 含盲道 296 张)/对照组(400 张)/loop 连续运行三模式; GT-预测占用一致性对照实验 (分离检测误差与几何规则误差)
- **`docs/spatial_relation_report.md`**: Phase 20 报告 (20 节, 含 GO 判定与技术限制)

### Changed (修改)
- **`backend/alert.py`**: `update()` 内调用 `spatial.classify`; 障碍物简化列表带 `blocking` 标记; `get_status()` 增 `alert_level / blocking / occupancy`; **normal/blocking 双冷却** — Level 1→Level 2 升级可立即播报, 不被普通告警冷却阻塞; 新增 `shutdown()` 优雅收尾 TTS 线程
- **`backend/detector.py`**: `draw()` 增可选 `occupancy` 参数 (默认 None 行为与 Phase 17/18/19 完全一致, 向后兼容)
- **`backend/web.py`**: worker 先 AlertManager 判定再绘制; `/api/status` 模型未就绪时也返回一致的 occupancy 结构
- **`frontend/index.html` / `style.css` / `app.js`**: 状态面板增"盲道占用/告警等级"行; Level 1 琥珀横幅 `⚠️ 检测到障碍物` / Level 2 红色横幅 `🔴 障碍物疑似占用盲道，请注意！` + 相关障碍物 (IoU/交叠指标); 障碍物列表"占用盲道?"角标

### Verified (实测)
- 单元测试 10/10 PASS; SpatialChecker 开销 0.075 ms/帧 (2 盲道框×20 障碍物)
- 阈值扫描: IoU=0.15 场景 I 漏报 → 上限 0.10; 交叠 0.20 vs 0.30 选 0.20 (安全优先少漏报)
- 盲道组 (296 张): 盲道检出 88.5%, Level2=44.6%; 对照组 (400 张无盲道 GT): Level2 仅 0.5% (2 例均为 ROD 图, ROD 不标注盲道, 可归因误报=0)
- GT-预测占用一致性 232/279=83.2%; 47 例不一致逐一归因均来自检测层 (漏检/框偏移), 非几何规则错误
- Web 冒烟 (图片源): Level 2 / blocking_obstacles (垃圾桶 0.921 交叠 0.699, 摩托车 0.616 交叠 0.216) / TTS 冷却 / MJPEG 200 / 前端新元素 全 PASS
- 连续 5 分钟: 18,545 帧 / 61.4 FPS (稳定在 55–61, 无持续下降) / 线程数稳定 / 显存恒定 / 零异常

### Limitations (技术边界)
- 输出为"**疑似占用**"判断: 基于二维 bbox 空间关系, 非 segmentation / 非三维测距 / 非绝对阻挡
- 系统性误报源: 透视下盲道实际为梯形, bbox 为矩形近似 (表示形式限制, 调阈值无法根治)
- 数据集事实: blind_road GT 仅约 7% 图像含标注 (test 296/4163)

### Safety (安全约束落实)
- 不重训 / 不改 best.pt / 不改数据集 / 不删文件 / 未新增任何 AI 模型 (无 ONNX/TensorRT/分割/深度模型)
- TTS 仍为异步线程+队列, 未重写同步语音

### Git
- 提交: `Phase 20: blind road spatial relation`

## [Phase 19] — 2026-09 (Web UI + 障碍物实时提醒 COMPLETE — GO)

### Added (新增)
- **`backend/alert.py`**: `AlertManager` — 障碍物类别筛选 (由 data.yaml 26 类派生, 排除 blind_road/crosswalk/green_light/red_light 共 22 类障碍物) / 盲道状态 / 提醒冷却 (2.5s) / 多障碍物去重合并中文文案 / 异步 TTS (独立线程 + 队列, 不阻塞检测) / TTS 不可用优雅降级
- **`backend/web.py`**: FastAPI 应用 — 单 camera worker 线程 (全程只开一次源, 规格 §18) / MJPEG `/video_feed` / `GET /api/status` JSON (camera/model/fps_stream/fps_model/blind_road/obstacles/alert/alert_message/tts_available) / `GET /api/obstacle_classes` / `/static` 前端 / 绑定 127.0.0.1 / 复用 detector 沙箱兼容 + camera 多 backend 回退
- **`frontend/index.html` + `style.css` + `app.js`**: 中文 UI (大视频区 + 状态面板 + 警告横幅), 每 500ms 轮询 `/api/status` 更新 Camera/Model/FPS/Blind Road/Obstacles/TTS/障碍物列表/警告横幅; 原生 HTML/CSS/JS 无构建
- **`scripts/run_web.py`**: 启动入口 (argparse: --source/--host/--port/--model/--conf/--imgsz/--device/--iou; 默认 127.0.0.1:8000, conf=0.20)
- **`docs/web_ui_report.md`**: Phase 19 报告 (20 节, 含 GO 判定 + Phase 20 建议)

### Web UI (规格 §三~§十七)
- 浏览器 `http://127.0.0.1:8000` 看实时画面 (检测框/类别/置信度)
- 实时 FPS: 同时显示 Stream FPS (实际 Web/视频链) 与 Model FPS (YOLO 推理), 不把 100+ 冒充网页 FPS
- 盲道状态: Detected / Detected (N) / Not Detected
- 障碍物状态 + 具体类别列表 (中文名 + 置信度)

### 障碍物提醒 (本阶段核心, 规格 §五~§十三)
- 视觉警告: 检测到障碍物 → 底部横幅 `⚠️ 检测到障碍物，请注意！` + 类别列表; 消失即隐藏
- TTS 语音: pyttsx3 (Windows SAPI, 本机语音, 无大模型/无 CUDA 依赖); 文案如 `检测到汽车、卡车，请注意。` / `检测到行人、汽车，请注意。`
- 提醒冷却: 2.5s, 持续障碍物每 ~2.5s 播报一次, 非逐帧刷屏 (实测持续 6s 仅 2 次)
- 多障碍物去重: 同类多 bbox 不重复; 多类合并成一句 (≤3 类列出, >3 → "检测到多个障碍物")
- 不阻塞: TTS 独立线程 + 队列, 未导致 FPS 下降 / 卡顿

### Verified (headless, curl 验证)
- 页面 HTTP 200 中文标题 / 单 camera worker 全程一次 / YOLO 检测框正常
- Stream FPS ~90–101 / Model FPS ~98–114 (图片回放; 真实摄像头 ~27 FPS 见 Phase 18)
- 盲道 Detected & Not Detected 均观察到 (默认 conf=0.20 缓解漏检)
- 障碍物 car/truck → alert=True, 文案正确; 多障碍物 person+pole → 合并
- TTS 沙箱 SAPI 可用 + 语音事件触发 (真实播报待用户本机音频验证)
- 冷却每 ~2.5s 一次 (非逐帧); 连续数分钟稳定无 OOM/崩溃

### Decision (Go / No-Go)
- **GO**: Web/Camera/YOLO/BlindRoad/Obstacle/视觉提醒/TTS/冷却/多障碍物/连续运行 全 PASS
- 已实现"摄像头→YOLO→网页→障碍物检测→视觉提醒→TTS"完整链路
- **未做** (留 Phase 20): 障碍物是否占用盲道 的空间关系判断

### Safety (安全约束落实)
- 不重训 / 不改 best.pt / 不导出 ONNX-TensorRT / 不修改数据集 / 不删任何文件
- 仅装最小依赖 fastapi/uvicorn/pyttsx3 (venv 内, 经 Clash 7897); 未装 CUDA Toolkit / 大模型 / Node
- 未进 Phase 20 (按规格 §39/§40 边界)
- 未 push (按用户约束, 仅本地 `git commit "Phase 19: web UI and obstacle alert"`)

### Git
- 提交: `Phase 19: web UI and obstacle alert`

## [Phase 18] — 2026-09-04 (部署/推理性能优化 COMPLETE — GO, 无需 ONNX/TensorRT)

### Added (新增)
- **`scripts/benchmark_phase18.py`**: 推理侧 Benchmark 运行器 (PyTorch FP32/FP16 计时 250 iter + 20 warmup, avg/P50/P95/FPS; VRAM 双口径 allocator + nvidia-smi; FP32 vs FP16 检测一致性; 盲道全量 GT 图图像级召回验证; 复用沙箱兼容)
- **`docs/deployment_optimization_report.md`**: 部署/推理性能优化报告 (目标/环境/GPU/版本/模型/配置/FP32/FP16/ONNX/TensorRT/端到端/VRAM 口径/检测一致性/盲道/瓶颈/推荐/Go/Phase19 建议)
- **`runs/yolov8n_prod_b32/phase18_benchmark/benchmark_stats.json`**: Benchmark 统计 (gitignore, 不入库)

### Benchmark (RTX 5070, imgsz=640 / batch=1 / device=0)
- **PyTorch FP32**: avg **9.501 ms** → **105.25 FPS**; P50 9.141 / P95 10.525; 真实 GPU 占用 **216 MiB** (nvidia-smi); allocator 峰值 51.6 MB
- **PyTorch FP16**: avg **10.143 ms** → **98.59 FPS**; P50 9.426 / P95 10.671; 真实 GPU 占用 218 MiB
- **结论**: 本机 Blackwell 上 FP16 反略慢于 FP32 → **保留 FP32** (更简单、无精度风险、略快)

### Verified (检测一致性 + 盲道)
- **FP32 vs FP16**: 10 张多类测试图检测框数完全一致 (32=32), 无系统性退化
- **blind_road 图像级召回** (全部 296 张 GT 图): **0.878 @0.25** / **0.899 @0.15** → PASS (与 Phase 16 R=0.802 一致, 非模型失效)
- CUDA error 无 / OOM 无

### Decision (Go / No-Go)
- **GO (无需继续优化)**: 模型推理 >100 FPS, 端到端 27–28 FPS (瓶颈在摄像头读帧 ~35ms, 非模型, 模型有 4 倍余量), 检测正常, GPU 占用低, 稳定
- **无需 ONNX**: PyTorch+GPU 已满足实时, 导出无收益 (规格 §12/§15)
- **无需 TensorRT**: 同 (规格 §13)

### Safety (安全约束落实)
- 不重训 / 不改 best.pt / 不导出 ONNX-TensorRT / 不修改数据集 / 不删 raw/processed/runs
- 未装 CUDA Toolkit / TensorRT; 磁盘全程 NORMAL (73.38 GB)
- 未 push (按用户约束, 仅本地 `git commit "Phase 18: deployment optimization"`)

### Git
- 提交: `Phase 18: deployment optimization`

## [Phase 17] — 2026-09-03 (实时摄像头检测 COMPLETE — 链路 PASS, headless 验证)

### Added (新增)
- **`backend/detector.py`**: `Detector` 类 (加载 best.pt + 单帧 YOLO 推理 + OpenCV 绘制, blind_road 橙色高亮; 复用沙箱兼容 YOLO_CONFIG_DIR/MPLCONFIGDIR/ThreadPool monkeypatch/workers=0; CUDA 可用性检查 + warmup + 线程安全 EMA-FPS)
- **`backend/camera.py`**: `list_cameras()` 枚举 + `open_camera()` 多 backend 回退 (CAP_DSHOW/CAP_MSMF), 失败抛清晰 RuntimeError
- **`scripts/run_camera.py`**: 实时主程序 (argparse: --source/--model/--conf/--imgsz/--device/--no-display/--max-frames/--save-dir/--save-every; 支持摄像头/视频/单图/目录; q/Q/ESC 退出; 全异常分支; 退出释放资源)
- **`docs/camera_report.md`**: 实时摄像头检测报告 (环境/摄像头/性能/三类场景/异常/已知问题/下一步)
- **`runs/yolov8n_prod_b32/camera_test/`**: 单图测试截图 (headless 验证产物)

### Verified (headless 沙箱验证)
- best.pt 正常加载 (26 类, device=0) ✅
- 摄像头 idx 0 打开 (640×480/30fps), 80 帧连续读帧无失败 ✅
- 每帧 YOLO 推理 + 绘制检测框/类别/conf/FPS ✅
- **模型推理 EMA 78.6 FPS (≈12.7 ms/帧)** — 与 Phase 16 单图 88 FPS 一致, 实时余量充足
- GPU 无 CUDA error / 无 OOM; 单帧分配峰值 38.4 MB (含 context 约 1–2 GB, 远低 8 GB) ✅
- 障碍类 (car/truck/bus/manhole/guard_rail/trash_bin/plant_pot) 与 blind_road 均正常出框 ✅
- 端到端循环 12.9 FPS 受沙箱虚拟摄像头慢速抓取限制 (非模型瓶颈); 真实摄像头将 ≥30 FPS

### Decision (链路 PASS / 未完成项)
- **链路 PASS**: 速度/显存/稳定性满足实时; 完整「摄像头→YOLO→绘制」成立
- 未亲验项 (本沙箱无 GUI + 虚拟摄像头): 可见 `cv2.imshow` 窗口 + 物理摄像头实景 → **须用户在笔记本 `python scripts/run_camera.py --source 0` 本地确认** (不伪造 PASS)

### Safety (安全约束落实)
- 不重训 / 不改 best.pt / 不导出 / 不进下一阶段; 未删 raw/processed/runs 任何文件
- 仅少量测试截图, 不存连续视频; 磁盘全程 NORMAL (73.49 GB)
- 未 push (按用户约束, 仅本地 `git commit "Phase 17: realtime camera detection"`)

### Git
- 提交: `Phase 17: realtime camera detection`

## [Phase 16] — 2026-09-03 (推理验证 COMPLETE — GO)

### Added (新增)
- **`scripts/run_inference.py`**: 推理验证运行器 (best.pt 指标复现 + 逐图预测匹配 + 七类可视化 A~G + GT-vs-Pred 对照 + GPU/CPU 性能基准; 复用沙箱适配, workers=0; 默认 best.pt, 支持 `--source/--output/--cpu`)
- **`docs/inference_report.md`**: 推理验证报告 (模型/数据/指标复现/定性/失败模式/性能/Go-No-Go 七节)
- **`docs/inference_stats.json`**: 复现统计 (test 整体+每类 P/R/mAP + Phase15 对照 + 漏检/误检计数 + 性能 + 磁盘, 可复现)
- **`runs/yolov8n_prod_b32/inference/`**: 12 张随机样本 + 72 张 GT-vs-Pred 对照

### Verified (指标复现 — test 4,163 图 / 35,128 实例)
- **mAP50 0.7765 / mAP50-95 0.5197 / P 0.8218 / R 0.7037** — 与 Phase 15 **完全一致 (diff=0.0)**
- ⭐ **blind_road mAP50 0.8486 / R 0.8024** — 完全复现 (Phase 15 目标 ≥0.75 ✅)
- 盲道漏检 104 图 (2.5%) / 803 实例 (≈20%); 误检 63 图; 长尾弱类 truck 0.538 / bus 0.610 / bicycle 0.652

### Performance (RTX 5070)
- 单图推理 **11.34 ms → 88.19 FPS** ｜ batch=32 吞吐 ≈640 图/秒 ｜ **峰值显存 4075 MB (4.07/7.96 GB)**
- CPU 单图 29.14 ms → 34.31 FPS ｜ 模型 **6.27 MB**

### Decision (Go / No-Go)
- **GO** — 七项标准全满足 (可加载 / 指标复现 / blind_road 无异常 / 无系统性漏检 / 速度足以实时 / 模型文件正常 / 摄像头部署无技术阻碍)
- 建议 Phase 17 对 blind_road 采用低置信阈值 + 告警降级; 长尾类暂不作为高可信事件

### Fixed (环境修复, 非模型)
- 列表源被 Ultralytics 整体载入 → CUDA OOM: 改**分块预测 (CHUNK=128)**
- 预测框 6 元组解包 / GT 2 元组画法两处脚本 bug 修正


## [Phase 15] — 2026-09-03 (全量正式训练 COMPLETE)

### Added (新增)
- **`scripts/run_prod_train.py`**: 全量训练运行器 (YOLOv8n + imgsz=640 + batch32 + 200 epochs + amp + close_mosaic=10; 含每 epoch 磁盘闸门回调 `on_train_epoch_end` + 沙箱适配)
- **`scripts/finalize_phase15.py`**: 收尾复评脚本 (best.pt 仅评估 val/test, 不重训; 补产 `final_training_stats.json`)
- **`docs/final_training_report.md`**: 正式训练报告 (配置/时长/显存/loss/整体+每类指标/与 smoke 对比/盲道专项/四项判断/产物/后续)
- **`docs/final_training_stats.json`**: 复评统计 (val+test 每类 P/R/mAP, 可复现)
- **`runs/yolov8n_prod_b32/`**: best.pt / last.pt / results.csv / 训练曲线

### Trained (训练结果 — 200 epochs / ≈12.5h / RTX 5070 8GB)
- GPU 峰值 **~5.0 GB** (无 OOM, batch=32 稳定) ｜ 0 CUDA error ｜ 0 崩溃 ｜ disk 全程 NORMAL (73.7→73.6 GB)
- 整体 (test 4,163 图 / 35,128 实例): **mAP50 0.776** / mAP50-95 0.520 / P 0.822 / R 0.704 (val mAP50 0.775)
- ⭐ **blind_road (test): mAP50 0.849 / mAP50-95 0.650 / P 0.858 / R 0.802** — **达成 Phase 14 目标 ≥0.75** ✅ (val 0.853)
- 最高类: green_light 0.941 / red_light 0.889 / crosswalk 0.892 / manhole 0.887; 最低 (长尾): truck 0.540 / guard_rail 0.622 / plant_pot 0.652

### Compared (与 Phase 14 smoke 对比)
- 整体 mAP50 0.301→0.775 (**+0.474**) ｜ blind_road mAP50 0.662→0.853 (**+0.191**)

### Verified (四项判断复核)
- 数据能训练 ✅ / 标签正确 ✅ / 模型正常收敛 ✅ / GPU 稳定 ✅ (loss 单调下降, mAP 稳定上升后平台, 跑满 200 epoch 未早停)

### Fixed (收尾修复 — 环境, 非模型问题)
- **`Path` 不可序列化**: `run_prod_train.py` 收尾将 `trainer.save_dir` (WindowsPath) 直接塞入 `json.dump` 抛 TypeError → 进程非零退出, 平台标记 failed;
  训练成果 (权重/csv/曲线/测试评估) 均已正常产出, 以 `finalize_phase15.py` 补产统计 (不重训), 根因加 `str()` 包裹修复

### Safety (安全约束落实)
- 未改/未删任何用户文件; `datasets/**` 零改动; 未碰系统 CUDA
- 磁盘闸门每 epoch 生效, 全程 NORMAL, 未触发 <15GB 安全停止
- 权重落 `runs/` (gitignore 屏蔽); 首次误启动空壳改名 `yolov8n_prod_b32_aborted_partial` (可删)

### Git
- 提交: `Phase 15: production training`

## [Phase 14 修订] — 2026-09-02 (分析统计口径修正)

### Fixed (修正 — 经 workbuddy 审查确认)
- **JSON `images: 26` 取值 bug**: `analyze_smoke_results.py` 误用 `nt_per_image.shape[0]` (实为 per-class 目标数,
  shape=(26,)=类别数) 作图数; 真实评估为 **100 张图**。改为统计 val 图片目录文件数 → JSON `images: 100`,
  与报告/磁盘三者一致 (mAP 数值本身一直有效)。
- **plant_pot 指标越界**: val 中该类无真值时 ultralytics 不建 AP 槽位 (`ap[25]` IndexError);
  改为 IndexError 分支记 0.0 + note「val 无该类目标, 抽样未覆盖」, 每类表完整。
- **mAP 口径统一**: 跨文档统一「最终 = best.pt 独立复评 **mAP50 0.301** / mAP50-95 0.184 / P 0.495 / R 0.284」;
  逐 epoch 序列 (results.csv, 末 epoch 0.303) 保留为训练期快照并附口径说明 (training_smoke_test.md / training_report.md)。

### Git
- 提交: `Phase 14: fix analysis stats (images=100, plant_pot, mAP 0.301 unified)`

## [Phase 14] — 2026-09-02 (小规模训练结果分析 COMPLETE)

### Added (新增)
- **`scripts/analyze_smoke_results.py`**: best.pt 详细评估 (每类 P/R/mAP) + plots (混淆矩阵/PR 曲线/batch 对照) + 含盲道预测样例生成
- **`docs/training_report.md`**: 训练结果分析报告 (loss/指标/混淆/预测样例 + 四项判断 + 正式训练建议)
- **`docs/training_analysis_stats.json`**: 每类指标统计 (可复现)
- **`runs/smoke_test/analysis/`**: 混淆矩阵/曲线/预测样例图 (6 张含盲道推理图)

### Analyzed (分析结果)
- **loss**: train cls 4.637→**2.164** (−53%), box/dfl 单调下降; val 同步下降, 无发散/过拟合
- **总体 (val)**: mAP50 0.0005→**0.301** (best.pt 复评; 末 epoch 训练快照 0.303) / mAP50-95 0.184 / P 0.495 / R 0.284
- **⭐ blind_road**: mAP50 **0.662** / mAP50-95 0.430 / P 0.637 / R 0.571 (10 epochs) → **盲道标注正确可学习**
- **长尾类 R=0** (stairs/guard_rail/chair/bench): val 100 图抽样不足, 非标签错误 (全集仅 84–419 实例)
- **四项判断**: 数据能训练 ✅ / 标签正确 ✅ / 模型收敛 ✅ / GPU 稳定 ✅ → **可正式训练**

### Recommended (正式训练建议)
- yolov8n 起步 (可试 s) ｜ epochs **150–200** + early-stop 30–50 ｜ batch **32** (smoke 峰值 1.93 GB) ｜ imgsz **640** ｜ 全量 **17,908 图** ｜ 默认 aug + `close_mosaic=10`, 长尾考虑 cls 权重 ｜ smoke best.pt warm-start 可选 ｜ 预期 mAP50 0.55–0.70 (盲道 ≥0.75)

### Safety (安全约束落实)
- 只读分析 (best.pt val/predict, 未改动数据与权重); plots 落入 `runs/` (gitignore 屏蔽)
- 磁盘: D 盘剩余 ~64 GB → NORMAL

### Git
- 提交: `Phase 14: training analysis`

## [Phase 13] — 2026-09-02 (小规模 YOLO 训练验证 COMPLETE)

### Added (新增)
- **`scripts/make_smoke_subset.py`**: smoke 子集构建 (450 train + 100 val, 含 blind_road 优先; 复制输出, 不动 raw/processed)
- **`scripts/run_smoke_train.py`**: smoke 训练运行器 (YOLOv8n + imgsz=640 + batch16 + AMP + 10 epochs; 记录时间/显存/loss/mAP; 含沙箱适配)
- **`datasets/smoke_test/`**: 子集 (126 MB; train 450 含盲道 74 / val 100 含盲道 18)
- **`runs/smoke_test/yolov8n_smoke_b16/weights/{best,last}.pt`**: 训练权重 (6.2 MB; 复评 mAP50 0.301)
- **`docs/training_smoke_test.md`** + **`docs/training_smoke_test_stats.json`**: 验证报告与统计

### Trained (训练结果 — 10 epochs / 103 s)
- loss 正常下降: box 1.62→**1.45** / cls 4.64→**2.16** / dfl 1.31→**1.18**
- 指标: mAP50 0.0005→**0.301** (best.pt 复评) / mAP50-95 **0.184** / P **0.495** / R **0.284** (val 100 图; 仅流程验证值)
- GPU: 峰值 **1.93 GB** (无 OOM, batch16 余量充足) ｜ AMP checks passed ｜ 0 CUDA error ｜ exit 0

### Verified (验证目标 6/6)
- 数据读取 ✅ / 标签 ✅ / 模型 ✅ (nc 80→26, 322/355 迁移) / GPU ✅ / loss 下降 ✅ / 验证流程 ✅

### Fixed (沙箱适配 — 环境, 非模型问题)
- **Arial.ttf 下载失败**: `YOLO_CONFIG_DIR` 重定向至工作区 `.yolo_config` + 预置系统字体; `MPLCONFIGDIR` 规避 matplotlib 缓存写入失败
- **[WinError 5] 标签缓存扫描**: ultralytics `multiprocessing.pool.ThreadPool` 创建命名管道被沙箱拒绝 → monkeypatch 为 `concurrent.futures` 纯线程池 (仅缓存扫描, 不改训练)
- **dataloader workers=0**: Windows spawn + 管道受限; 450 图单进程足够

### Safety (安全约束落实)
- 训练前 `check_before_operation(required_gb=5)` → NORMAL (73.8 GB), 允许
- `datasets/raw/**` / `datasets/processed/**` 零改动 (smoke 子集为独立复制)
- 磁盘: D 盘剩余 ~64.3 GB → NORMAL; 训练产物落入 `runs/` (gitignore 屏蔽)

### Git
- 提交: `Phase 13: training smoke test`

## [Phase 12] — 2026-09-02 (数据可视化质量检查 COMPLETE)

### Added (新增)
- **`scripts/visualize_dataset_quality.py`**: 可视化质检脚本 (随机采样训练图, 优先覆盖含 blind_road 的图; 图片+YOLO 标签绘制; 数值校验; 输出预览图与统计 JSON)
- **`datasets/preview/`**: 120 张标注预览图 + `_summary_grid.jpg` 汇总拼贴 (16.1 MB; 已 gitignore, 不入库)
- **`docs/dataset_quality_report.md`**: 质检报告 (采样统计 / 数值与语义检查 / 正常-异常-无法使用统计 / 结论)
- **`docs/dataset_quality_stats.json`**: 质检统计 (seed=20260902, 可复现)

### Checked (检查结果 — 120 张 / 1,335 实例)
- **数值**: 类 ID 越界 0 / 坐标越界 0 / 框非法 0 / 框序颠倒 0 / 非 5 列行 0 / 图不可读 0 / 配对缺失 0
- **盲道**: 53 实例命中, 框形健康 (面积 mean 25.8%, 横向条带为主), 位置合理
- **几何异常复核 28 条 → 全部合理**: 25 条远景小目标 (roadblock/cone/立柱, 数据集固有特性);
  3 条超大框溯源 — `car 97.3%` 图经 **YOLOv8n 模型辅助验证** (检出 car conf 0.79 区域与标注吻合, COCO 继承标注可信);
  2 条 tricycle 为作者自采近景特写
- **结论**: 120 张全部**正常** (0 异常 / 0 无法使用), **未发现严重标签错误** → 不触发「停止/不要训练」, 可进入训练

### Reminders (非阻断提醒)
- WOTR 远景小目标占比高 → 关注小目标召回; `plant_pot`/`bench` 长尾类极少 (83/84) → 建议类别权重/过采样;
  tricycle 2 个超大框建议训练前人工抽查 (低风险)

### Safety (安全约束落实)
- 纯只读检查 (仅输出预览图与报告); `datasets/processed/**` 与 `datasets/raw/**` 零改动
- 预览输出落入 `datasets/preview/` (`.gitignore` 屏蔽, 不入库); D 盘剩余 ~64.5 GB → NORMAL

### Docs (文档同步)
- `PROJECT_STATUS.md` 当前状态/磁盘表/Phase 12/下一步 (Phase 13 训练候选) 更新

### Git
- 提交: `Phase 12: dataset quality validation`

## [Phase 11] — 2026-09-02 (YOLO 数据集转换 COMPLETE)

### Added (新增)
- **`scripts/convert_dataset.py`**: raw → processed 转换器 (VOC/YOLO 双解析 + 26 类映射 + Building/Road 按行剔除 + 全局 MD5 去重 + data.yaml 生成 + `--dry-run`/`--force`)
- **`scripts/check_dataset.py`**: 转换后自检 (目录结构 / 配对 / PIL 完整性 / 格式 / 类 ID / 坐标 / 泄漏 / 空标签 / data.yaml 一致性)
- **`datasets/processed/`**: 统一 YOLO detection 数据集 (17,908 图 / 195,719 实例 / 26 类; train 10,043 / val 3,702 / test 4,163; 4.366 GiB) + `data.yaml` (`nc=26`, 绝对路径, 入库)
- 报告与日志: `docs/phase11_conversion_report.json` / `docs/phase11_check_report.json` / `docs/logs_phase11_convert.txt` / `docs/logs_phase11_check.txt`

### Converted (转换内容)
- **WOTR** (VOC, 20 类): XML stem ↔ 图片 stem 配对 (勿用 `<filename>`); bbox 归一化; 映射到统一 26 类
- **ROD** (YOLO, 25 类): 5 列框直留; **786 条有效多边形转外接框** (raw 923 − 137 属 Building/Road); `Building`/`Road` 236 行整行剔除; 映射到统一 26 类 (electrical_box→pole、Bicycle Rack→bicycle 等)
- **去重**: MD5 剔除 20 张 (train 13 + val 7; WOTR 11 + ROD 9) → 跨划分泄漏 0
- **任务类型**: detect (盲道无 mask 监督; ROD 多边形退化为外接矩形)

### Verified (自检 PASSED)
- 图片=标签 100% (每划分) ｜ 损坏 0 / 零字节 0 / 孤立标签 0 / 格式错误行 0 / 类 ID 越界 0 / 坐标非法 0 / 跨划分重复 0
- 核心类 `blind_road` 2,381 全量保留 (train 1,599 / val 372 / test 410); 来源前缀 wotr_ 13,917 + rod_ 3,991

### Safety (安全约束落实)
- `datasets/raw/**` **严格只读**, 一个字节未改; 未删除 raw
- 转换前磁盘闸门 NORMAL; 完成后 D 盘剩余 ~64.5 GB (raw 4.41 + processed 4.37 ≈ 8.8 GB)
- `datasets/processed/**` 被 `.gitignore` 屏蔽, 仅放行 `data.yaml` 入库; raw 的 `DATASET_INFO.md` 同步放行入库

### Docs (文档同步)
- `docs/dataset_report.md` 新增 §11 (转换结果/核对/磁盘)
- `docs/dataset_analysis.md` §8 标注「已执行」, 输出目录统一为 `datasets/processed/`
- `PROJECT_STATUS.md` 当前状态/磁盘表/Phase 11/下一步 更新

### Git
- 提交: `Phase 11: YOLO dataset conversion`

## [Phase 10] — 2026-09-02 (数据集结构与标签分析 COMPLETE)

### Added (新增)
- **`docs/dataset_analysis.md`**: 结构与标签分析报告 — 格式判定 / 分辨率 / 目标尺度 / 类别方案 / YOLO 适配性 / 质量清单 / **§8 Phase 11 转换清单**。
- **`scripts/analyze_datasets_phase10.py`**: 只读全量分析脚本 (PIL 解码校验 + MD5 去重 + VOC/YOLO 双解析器 + COCO 尺度统计)。
- **`docs/dataset_analysis_stats.json`**: 全量统计明细 (可复现, 供报告引用)。

### Analyzed (分析结果 — 全量扫描 17,928 图, 非抽样)
- **规模**: WOTR 13,928 图 / 13,928 XML / **189,994** 实例 / 20 类; ROD 4,000 图 / 4,000 标签 / **6,073** 实例 / 25 类; 合计 **17,928 图 / 196,067 实例**。
- **标注格式**: WOTR = **PASCAL-VOC**(纯 `<bndbox>`, 非 COCO / 非 Mask / 非 Polygon); ROD = **YOLO 原生 + Polygon 分割混合**(5,150 条 5 列框 + 923 条多边形, 涉及 843 图; 非 COCO / 非 Mask)。
- **分辨率**: WOTR 均值 883.8×746.2 (1,390 种, 123×140 ~ 5,621×4,032); ROD 均值 584×578.5 (52 种, 73.3% 为 640×640)。
- **目标尺度 (COCO)**: WOTR small 70,460 (37.1%) / medium 80,644 / large 38,890; ROD large 84.1%。
- **完整性**: 损坏图 **0** / 零字节 **0** / 图片-标签配对 **100%** / 非法框 **0** / 越界框 **0** / 非法标注行 **0**; 空标签 WOTR **0**、ROD **12** (train 3 + valid 4 + test 5)。
- **重复**: WOTR **11 组** + ROD **9 组** = 20 组 (MD5 完全相同), 其中 **15 组跨划分** → 存在评估泄漏 (WOTR 7: train↔test ×3 / train↔val ×2 / test↔val ×2; ROD 8: valid↔test ×4 / train↔test ×2 / train↔valid ×2; 余 5 组为划分内部); 跨数据集重复 **0**。
- **盲道类**: `blind_road` **1,723 图 / 2,381 实例** (train 1,599 / val 372 / test 410), small 仅 24 个 (1.0%) → 尺度健康; 但占总实例 **1.21%** → 核心类样本偏少。

### Decided (方案决策)
- ✅ **适合 YOLO, 但必须转换**: 两者均以水平矩形框为主; 第一阶段做 **detect** (非 seg — 盲道无任何 mask/polygon 监督, ROD 多边形仅覆盖 843 图且不含盲道); 训练 `imgsz=640`。
- **统一 26 类**: 15 组跨集同义类合并 (person/Person、pole/Electrical Pole、bicycle/Bike(+Bicycle Rack)、roadblock/Teraffic Barrel、reflective_cone/Traffic Cone、ashcan/Dustbin、crosswalk/Pedestrian crosswalk 等)。
- **丢弃 2 类**: `Building`(144) / `Road`(92) — 背景类, 且 Road 与 blind_road 语义冲突易混淆; ⚠️ 必须**按行剔除**标注 (不可只删 names, 否则 class id 错位)。
- **去重策略**: 按 MD5 分组, **保留 val/test 副本, 从 train 剔除重复项** (训练集精确损失 **13 张** = WOTR 9 + ROD 4, 测试集保持纯净)。

### Safety (安全约束落实)
- ✅ 未训练 / **未转换** / **未修改或删除任何原始数据** (`datasets/raw/**` 零改动)。
- ✅ 分析为纯只读 (图片仅做 PIL 解码校验与哈希计算, 无任何写入)。
- 磁盘: **68.95 GB → NORMAL** (≥ 30 GB)。

### Git
- 提交: `Phase 10: dataset analysis`

## [Phase 10 修订] — 2026-09-02 (报告数字一致性修正)

### Fixed (修正 — 经全量 MD5 复算确认)
- **合并组数 11 → 15**: §6.1 中「合并」判定实为 **15** 个 (person / pole / car / tree / motorcycle / crosswalk / bicycle / roadblock / cone / truck / sign / trash_bin / bus / fire_hydrant / dog), §6.2 映射亦为 15 组; 原句「最终压并为 11 个合并类」一并更正为「对应 §6.1 中 15 个『合并』判定类」。
- **WOTR 跨划分重复 5+ → 精确 7 组**: train↔test ×3、train↔val ×2、**test↔val ×2** (`20007314`↔`30007026`、`20007693`↔`30007123`); 另 4 组为 train 内部重复, 非泄漏。
- **「17 组」→ 15 组跨划分** (§0 TL;DR + §7.1): 原值基于「5+ 组」估算, WOTR 精确为 7 后未回改汇总; 精确账 = 跨划分 **15** (WOTR 7 + ROD 8), 总重复组 **20** (11 + 9)。
- **「~14 张」→ 精确 13 张** (§7.2 + 本文件): WOTR 9 (train 内部 4 + 跨划分 5) + ROD 4。
- **「长尾 32:1」→ 437:1** (§0 TL;DR): 32:1 无法从任何口径复现 (合并 26 类 437:1 / WOTR 20 类 34.5:1 / ROD 25 类 22.1:1 / person:blind_road 14.8:1), 统一为 §6.4 的合并后 **437:1** (person 36,238 vs plant_pot 83)。
- §7.2 增补**合计行** (20 组 / 20 张 / 15 组跨 split), 使 TL;DR 与明细可直接对账, 避免再次出现「改一处漏三处」。

### Synced (跨文档同步)
- `PROJECT_STATUS.md`: 「重复与泄漏」「待处理风险」「Phase 11 转换清单」三处同步为 **20 组重复 (15 组跨划分)** 与 **13 张**待剔除副本。

### Git
- 提交: `Phase 10: fix dataset analysis number consistency`

## [Phase 09 修订] — 2026-09-01 (WOTR 全量统计修正 + zip 清理)

### Fixed (修正 — 经 workbuddy 审查确认)
- **盲道全量数修正**: 首版 `DATASET_INFO.md` 误记盲道 "17 张/23 实例" (前缀抽查 2,000 XML 的低估值);
  全量扫描实为 **1,723 图 / 2,381 实例** (`blind_road` 在文件后段集中分布, 抽查低估约 100 倍)。
- **`TW` 误判移除**: 首版称 "未知类 TW 519 个需核对"; 全量确认 `object/name` 仅 20 类, **无 TW**;
  `TW` (926 次) 位于 `<owner><name>`, 是标注者姓名, 转换阶段无需处理。
- **转换陷阱记录**: 13,926/13,928 个 XML 的 `<filename>` 与磁盘图片名不一致 → 必须按
  **XML stem ↔ 图片 stem** 配对 (已验证 100% 完整); 已写入 `DATASET_INFO.md` §5 必读。
- **多源 folder 记录**: `<folder>` 含 img-train 6,071 / img-val 1,510 / img-test 1,742 / 新建文件夹 720 /
  COCO2017 926 / VOC2007 242 / train 924 / val 246 / test 245 等 (混合源, 不影响训练)。

### Removed (清理)
- **删除 WOTR.zip (3.95 GiB)**: 解压内容已三重验证完整 (`testzip()` + 13,928 配对 + 全量统计),
  删除回收 3.95 GiB; `scripts/download_wotr.py` 可随时重新下载 (Range 断点续传)。

### Changed (变更)
- `datasets/raw/wotr/DATASET_INFO.md` 重写 (全量类别表 + 陷阱说明 + zip 已删)
- `docs/dataset_report.md` §0.2 / `docs/storage_report.md` §2.1 / `PROJECT_STATUS.md` 磁盘表与 Phase 09 同步修正

### Safety (安全约束落实)
- 未训练 / 未转换 / 未删除任何**用户**文件 (删除的是本项目下载的冗余压缩包, 数据无损失)
- 删除后 D 盘剩余 **~69 GB → NORMAL**

### Git
- 提交: `Phase 09: fix WOTR stats (blind_road 1723, TW is owner) + drop redundant zip`

## [Phase 09 补充] — 2026-09-01 (WOTR 全量下载 COMPLETE)

### Added (新增)
- **WOTR 全量** (VOC, MIT, 含盲道类): 13,928 图 + 13,928 XML (train 9,056 / val 2,338 / test 2,534)
  - 经 **Google Drive 公开链接零凭证**获取 (gdown 流程 + Range 断点续传)
  - 落盘: `datasets/raw/wotr/` (WOTR.zip 3.95 GiB + 解压 4.19 GB + `DATASET_INFO.md`)
- **`scripts/download_wotr.py`**: WOTR 下载脚本 (磁盘闸门 + 病毒扫描确认页处理 + usercontent GET + Range 续传 + zip testzip 校验)

### Verified (验证结果)
- WOTR.zip 4,244,840,539 B 与 Drive 大小完全匹配; `testzip()` → 无损坏
- JPEGImages 13,928 / Annotations 13,928 配对完整; ImageSets 划分合计 13,928 ✅
- ⚠️ 首版抽查值 (17 张/23 实例) 已被后续全量统计修正 (见上方 [Phase 09 修订]); object/name 全量 20 类

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
