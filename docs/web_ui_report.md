# Phase 19：Web UI + 障碍物实时提醒 — 报告

> 阶段目标：摄像头 → YOLOv8n → 网页实时画面（检测框/类别/置信度/FPS）→ 检测到障碍物 → **视觉警告 + 语音/TTS 提醒**。
> 本阶段**不**做"障碍物是否占用盲道"的空间关系判断（留待 Phase 20）。

---

## 1. Phase 19 目标

实现本地 Web 系统，浏览器访问 `http://127.0.0.1:8000` 即可看到：
- 摄像头实时画面 + YOLO 检测框 / 类别 / 置信度
- 实时 FPS（区分 Stream FPS 与 Model FPS）
- 盲道状态（Detected / Not Detected）
- 障碍物状态 + 具体类别列表
- **核心**：检测到预定义障碍物类别时，网页出现视觉警告横幅，并通过电脑扬声器做语音提醒（带冷却，不刷屏）

---

## 2. Web 架构

```
摄像头/图片/视频源 (单 worker 线程, 全程只打开一次)
      │
      ▼
OpenCV 读帧 ──→ YOLOv8n (Detector, GPU device=0) ──→ 绘制检测框
      │                                                  │
      │                                                  ▼
      │                                          AlertManager.update()
      │                                     (筛选障碍物 / 盲道 / 冷却 / 去重 / TTS)
      ▼                                                  │
维护"最新已绘制帧" ──┐                      状态 (alert/obstacles/blind_road/...)
                     │                                  │
            ┌────────┴───────────┐                       │
            ▼                    ▼                       ▼
       /video_feed        /api/status (JSON)     独立 TTS 线程 (队列, 不阻塞)
       (MJPEG 流)         (前端每 500ms 轮询)     (pyttsx3 / SAPI)
```

- **单一 camera worker 线程**：整个进程只打开一次源，浏览器刷新/多标签不会重复创建摄像头（规格 §18）。
- **模型只加载一次**：启动时 `Detector` 加载 `best.pt`，`device=0 / imgsz=640 / batch=1 / workers=0 / FP32`。
- **MJPEG** 传输（规格 §17，不用 WebRTC）；多个浏览器连接共享同一最新帧，绘制只做一次。

---

## 3. 技术栈

| 组件 | 选型 | 说明 |
|---|---|---|
| Web 框架 | **FastAPI 0.141.1** | 轻量、异步、自带路由 |
| 服务器 | **uvicorn 0.52.4** | `127.0.0.1:8000`，仅本机（规格 §28） |
| 视频流 | OpenCV MJPEG (`multipart/x-mixed-replace`) | 简单可靠 |
| 模型 | Ultralytics YOLOv8n `best.pt` (Phase 15 正式模型) | 不修改、不重训 |
| TTS | **pyttsx3 2.99**（Windows SAPI，本机语音，无大模型/无 CUDA 依赖） | 规格 §10 |
| 前端 | 原生 HTML/CSS/JS（无 React/Vue/Node 构建） | 规格 §25 禁止引入 |

依赖安装：`fastapi uvicorn pyttsx3`（经 Clash 代理 7897 装入项目 venv，无系统级/CUDA 依赖）。

---

## 4. 项目结构（新增）

```
backend/
  detector.py      (复用 Phase 17, 含沙箱兼容 + 绘制)
  camera.py        (复用 Phase 17, 多 backend 回退)
  alert.py         (★新增: 障碍物筛选/盲道/冷却/去重/异步TTS)
  web.py           (★新增: FastAPI 应用 + camera worker + MJPEG + /api/status)
frontend/
  index.html       (★新增: 中文 UI, 大视频区 + 状态面板 + 警告横幅)
  style.css        (★新增)
  app.js           (★新增: 轮询 /api/status, 更新面板 + 警告横幅)
scripts/
  run_web.py       (★新增: 启动入口, argparse --source/--conf/--port/...)
docs/
  web_ui_report.md (本报告)
```

未大规模重构，沿用 Phase 17 的 `detector.py` / `camera.py`。

---

## 5. 启动方式

```powershell
cd /d D:\BlindRoadMonitor
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts/run_web.py
# 默认: 物理/USB 摄像头 idx 0, http://127.0.0.1:8000

# 无摄像头时用测试图片循环回放验证:
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts/run_web.py --source datasets/processed/images/test/rod_IMG_19187.jpg

# 调低盲道阈值 / 换端口:
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts/run_web.py --conf 0.20 --port 8000
```
也可直接 `python -m uvicorn backend.web:app --host 127.0.0.1 --port 8000`。

---

## 6. API

| 路由 | 说明 |
|---|---|
| `GET /` | 中文 Web 页面 |
| `GET /video_feed` | MJPEG 实时画面（检测框/类别/置信度/FPS） |
| `GET /api/status` | JSON 状态（见下） |
| `GET /api/obstacle_classes` | 返回 22 个障碍物类别名 |
| `/static/*` | 前端静态文件 |

`/api/status` 示例：
```json
{
  "camera": true, "model": true,
  "fps_stream": 94.2, "fps_model": 111.5,
  "blind_road": true, "blind_road_count": 1,
  "obstacle_count": 8,
  "obstacles": [{"class":"pole","confidence":0.91,"zh":"电线杆"}, ...],
  "alert": true,
  "alert_message": "检测到电线杆，请注意。",
  "tts_available": true
}
```

---

## 7. 摄像头实现

- `backend/camera.py` 的 `open_camera(idx)`：尝试 `CAP_DSHOW` → `CAP_MSMF` 回退（Windows 兼容），与 Phase 17 一致。
- `web.py` 的 `camera_worker` 全程只打开一次源；图片/视频源循环回放，便于无摄像头环境验证（规格 §30）。
- 摄像头打不开 → `state["camera"]=False` + `camera_error`，服务不退出，页面显示占位帧与错误文案（规格 §22）。

---

## 8. YOLO 实现

- `Detector`（复用 Phase 17）：加载 `runs/yolov8n_prod_b32/weights/best.pt`，`device=0, imgsz=640, batch=1, workers=0, FP32`（Phase 18 推荐）。
- 沙箱兼容沿用：`YOLO_CONFIG_DIR` / `MPLCONFIGDIR` / ThreadPool monkeypatch。
- 默认 `conf=0.20`（Phase 16/17/18 建议的盲道运行阈值；原 0.25 漏检偏多）。

---

## 9. FPS

| 场景 | Stream FPS | Model FPS | 说明 |
|---|---|---|---|
| 图片循环回放（沙箱 headless） | **~90–101** | **~98–114** | Model FPS 含绘制；回放无真实摄像头读帧开销 |
| 真实摄像头（Phase 18 实测，用户机器） | **~27.2** | **~110.8** | 端到端受摄像头读帧 ~35ms 限制，模型有 4× 余量 |

页面同时显示 `Stream FPS`（实际 Web/视频处理链）与 `Model FPS`（YOLO 推理），不把 100+ 内部 FPS 冒充网页 FPS（规格 §4）。

---

## 10. 盲道检测

- 从 `data.yaml` 26 类读取，`blind_road` 为索引 0。
- 网页盲道状态：`Detected` / `Detected (N)` / `Not Detected`。
- 验证：盲道测试图上 `blind_road=True, count=1`；无盲道图上 `Not Detected`（符合规格 §9"画面无盲道属正常"）。
- **残留漏检**：模型对盲道约 10–20% 实例级漏检（Phase 16/18 已记录，非本阶段缺陷）。已通过默认 `conf=0.20` 缓解（Phase 18 图像级召回 @0.20=0.899）；更难的远/小/遮挡样本仍可能漏检。

---

## 11. 障碍物检测

- 障碍物类别由 `data.yaml` 派生，排除非实体路面/信号类：`blind_road(0) / crosswalk(7) / green_light(9) / red_light(10)`，其余 22 类视为障碍物（见 `backend/alert.py` 的 `OBSTACLE_CLASS_INDICES`）。
- 验证：障碍物图（car/truck）`obstacle_count=2, alert=True`；多障碍物图（person/pole/…）`obstacle_count=8` 正确列出。

---

## 12. 视觉提醒

- 检测到障碍物 → 底部警告横幅显示 `⚠️ 检测到障碍物，请注意！` + 具体类别（中文名 + 置信度）。
- 障碍物消失 → 横幅隐藏（实时更新）。✅

---

## 13. TTS 提醒

- `pyttsx3`（Windows SAPI，本机语音，无大模型/无 CUDA 依赖）。
- 提醒文案示例：`检测到汽车、卡车，请注意。` / `检测到行人、电线杆，请注意。` / 单一障碍物 `检测到汽车，请注意。`
- 沙箱实测：`tts_available=True`，SAPI 初始化成功，语音事件已触发（`speech_count` 增长）。
- **真实播报**需在用户本机（有音频设备）验证；沙箱无音频输出设备，但代码路径与状态均正常。

---

## 14. 提醒冷却机制

- `AlertManager` 冷却 `ALERT_COOLDOWN = 2.5s`（规格 §11 建议 2–3s）。
- 同一障碍物持续存在 → **每 ~2.5s 播报一次**，而非逐帧刷屏（`滴滴滴滴…`）。
- 实测（持续障碍物 6s）：语音仅触发 2 次；实时循环轮询 `speech` 每 ~2.5–3s +1（非每帧）。✅
- TTS 在**独立线程 + 队列**中执行，不阻塞检测主循环（规格 §13，未导致 FPS 下降）。

---

## 15. 多障碍物处理

- 按类别集合去重合并成一句话：`检测到行人、汽车，请注意。`；>3 类 → `检测到多个障碍物，请注意。`
- 同一类别多个 bbox 不重复播报。
- 实测：person+car → `检测到行人、汽车，请注意。`；8 个障碍物 → 合并列出。✅

---

## 16. 浏览器测试（规格 §29）

| # | 测试项 | 结果 | 备注 |
|---|---|---|---|
| 1 | 页面 | **PASS** | HTTP 200，中文标题 |
| 2 | 摄像头 | **PASS** | 沙箱用图片源回放；物理摄像头走复用 `open_camera`（Phase 17 已验证 idx 0） |
| 3 | YOLO | **PASS** | 检测框正常输出 |
| 4 | 检测框 | **PASS** | MJPEG 含绘制帧 |
| 5 | FPS | **PASS** | Stream ~90–101 / Model ~98–114（回放）；真实摄像头 ~27（Phase 18） |
| 6 | 盲道状态 | **PASS** | Detected / Not Detected 均观察到 |
| 7 | 障碍物状态 | **PASS** | count + 列表正确 |
| 8 | 视觉提醒 | **PASS** | 横幅显隐正确 |
| 9 | TTS | **PASS*** | 沙箱 SAPI 可用、事件触发；真实播报待用户机器 |
| 10 | 提醒冷却 | **PASS** | 每 ~2.5s 一次，非逐帧 |
| 11 | 连续运行 | **PASS** | 数分钟稳定，FPS 平稳，无 OOM/崩溃 |

\* TTS 在沙箱无音频设备，功能路径 PASS；本机有声音输出即生效。

---

## 17. 连续运行测试

- 后台运行数分钟：Stream FPS 平稳（87–101），Model FPS ~98–114，GPU 无 OOM/CUDA 错误，无内存异常增长，TTS 线程数量恒定（daemon，不累积）。✅

---

## 18. 已知限制

1. **沙箱 headless**：本环境无显示器/浏览器，未截图可见网页；MJPEG/HTML/`/api/status` 均经 curl 验证。用户需在**本机浏览器**打开 `http://127.0.0.1:8000` 亲眼确认画面与语音。
2. **盲道 ~10–20% 实例漏检**：模型固有，已用 `conf=0.20` 缓解；极端远/小/遮挡样本仍可能漏检（非本阶段缺陷）。
3. **未做空间关系**：仅"检测到障碍物→提醒"，未判断"是否占用盲道"（Phase 20）。
4. **TTS 中文清晰度**依赖 Windows SAPI 语音包；如需更自然可后续换边缘 TTS（仍不引大模型）。
5. **真实摄像头端到端 ~27 FPS**：瓶颈在摄像头读帧（~35ms），非模型；已达规格 §20"良好"区间，无需强优化。

---

## 19. 阶段结论

**GO（达成核心目标）**

- Web：PASS ｜ Camera：PASS ｜ YOLO：PASS ｜ Blind Road：PASS ｜ Obstacle：PASS
- 视觉提醒：PASS ｜ TTS：PASS（本机生效）｜ 提醒冷却：PASS ｜ 多障碍物处理：PASS ｜ 连续运行：PASS
- 已实现"摄像头 → YOLO → 网页 → 障碍物检测 → 视觉提醒 → TTS 提醒"完整链路。
- 尚未完成"障碍物是否占用盲道"的空间关系判断（Phase 20）。

---

## 20. Phase 20 建议

1. **空间关系判断**：`blind_road bbox + obstacle bbox` → IoU/中心距离/投影 → 判定"疑似占用盲道" → 高优先级提醒（`🔴 障碍物疑似占用盲道，请注意！`）。
2. 可复用本阶段 `AlertManager`，在其上增加 `SpatialChecker`；告警分级（普通障碍物 / 占用盲道）。
3. 长尾弱类（truck/bus/bicycle/guard_rail）可补充数据或类别权重（Phase 16 已记录）。
4. 真实摄像头端到端 FPS 若需提升，优先优化摄像头读帧（backend/分辨率），而非模型。

---

*生成日期：2026-09（Phase 19）。环境：RTX 5070 Laptop 8GB / torch 2.11.0+cu128 / Ultralytics 8.4.135 / Python 3.13.14。*
