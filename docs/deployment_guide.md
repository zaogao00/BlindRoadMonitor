# 部署指南 — BlindRoadMonitor (Phase 21)

> 面向部署/维护者。普通使用者请看 `docs/user_manual.md`（只需双击 bat + 打开浏览器）。

---

## 1. 环境要求

| 项目 | 要求 | 本项目验证值 |
| ---- | ---- | ------------ |
| 操作系统 | Windows 10/11（64 位） | Windows 11 家庭中文版 |
| Python | 3.13.x | 3.13.14 |
| GPU | NVIDIA（CUDA 12.x 运行时兼容） | RTX 5070 Laptop 8GB（sm_120） |
| 显卡驱动 | 较新即可，**不需要装 CUDA Toolkit** | 591.86 |
| 摄像头 | 任意 DirectShow/MediaFoundation 兼容摄像头 | 内置/USB 均可 |
| 音频 | 可选（无音频时 TTS 优雅降级） | — |
| 磁盘 | 项目 + venv 约 9 GB | D 盘剩余 ≥30 GB 为 NORMAL |

**明确不需要**：CUDA Toolkit、TensorRT、ONNX Runtime、任何分割/深度模型、任何大型 TTS 模型。

## 2. 安装

```bat
cd /d D:\BlindRoadMonitor

:: 1) 隔离虚拟环境（不要装进系统/Anaconda）
<python 3.13> -m venv D:\BlindRoadMonitor.venv

:: 2) PyTorch CUDA wheel —— 必须使用 PyTorch 官方索引（已验证方案，勿改）
D:\BlindRoadMonitor.venv\Scripts\python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

:: 3) 其余依赖（requirements.txt 已锁定实际版本，含 fastapi/uvicorn/pyttsx3）
D:\BlindRoadMonitor.venv\Scripts\python.exe -m pip install -r requirements.txt

:: 4) 验证
D:\BlindRoadMonitor.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

模型权重 `runs\yolov8n_prod_b32\weights\best.pt`（5.98 MB，26 类）已随仓库提供，**无需下载**。

## 3. 启动

**一键（推荐给使用者）**：双击 `scripts\start_web.bat`（失败时窗口保持打开显示中文错误）。

**命令行（推荐给维护者）**：

```bat
cd /d D:\BlindRoadMonitor
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts\run_web.py
```

默认参数：`--source 0 --conf 0.20 --port 8000 --width 640 --height 480`。
日志出现 `[web][worker] 源已打开: kind=camera ...` 即摄像头就绪。

## 4. 浏览器访问

```text
http://127.0.0.1:8000
```

仅绑定 127.0.0.1，**不对外网开放**。Edge / Chrome 均可。

健康检查端点（用于脚本/监控）：

- `GET /api/health` — 服务存活探针（服务活着即 200，不因摄像头/模型故障变红）
- `GET /api/status` — 完整状态（含 `resolution / alert_level / occupancy / tts_available`）
- `GET /video_feed` — MJPEG 视频流
- `GET /api/obstacle_classes` — 22 类障碍物清单

## 5. 摄像头设置

- 默认 `--source 0`；多摄像头时用 `--source 1/2/...`
- `--width/--height` 是**软设置**：请求 640x480，摄像头不支持则沿用自身协商值，**不会因此启动失败**；实际结果看 `/api/status` 的 `resolution` 字段
- **故意不设置 FPS**：由摄像头自行协商，避免锁死 60FPS 导致打不开或卡顿
- 摄像头被占用/不存在：服务照常启动，页面 Camera 显示 Error（悬停看中文原因），其余功能不受影响

## 6. TTS 语音

- 引擎：pyttsx3 → Windows SAPI 本机语音，**离线、无大模型**
- 机制：**独立线程 + 队列（异步）**，不阻塞检测主循环
- 冷却：2.5 秒；Level 1 → Level 2 升级**立即**插播高级告警（双冷却设计）
- TTS 初始化失败（无声卡/驱动异常）：自动降级——画面与文字提醒照常，页面 TTS 显示"不可用"，**服务不崩溃**
- 沙箱环境无法证明真实扬声器输出，**最终声音验证须在 Windows 实机完成**

## 7. 常见错误

| 现象 | 原因 | 处理 |
| ---- | ---- | ---- |
| bat 提示"找不到虚拟环境 Python" | venv 被删/移动 | 按第 2 节重建 |
| `端口 8000 被占用` / 地址已占用 | 其他程序占了端口 | `--port 8010` |
| Camera = Error，提示"设备不存在/被占用" | 摄像头被相机/会议软件占用，或索引不对 | 关掉占用程序；`--source 1` 换索引 |
| `CUDA 不可用 ... is_available=False/...` | 驱动过旧 / 没有 NVIDIA 显卡 | 更新驱动；或 `--device cpu`（显著变慢） |
| `模型文件不存在` | best.pt 缺失 | 恢复 `runs\yolov8n_prod_b32\weights\best.pt` |
| 一直 Blind Road = Not Detected | 距离远/光线差/盲道磨损 | 靠近拍摄；`--conf 0.15` |
| 页面打不开但窗口无报错 | 端口不一致 | 看窗口里 `[web] 启动 http://127.0.0.1:<端口>` |

## 8. 性能说明（实测，RTX 5070 Laptop）

| 场景 | 数值 |
| ---- | ---- |
| YOLO 纯推理（FP32, imgsz640） | ~9.5 ms/帧 ≈ 105 FPS（Phase 18） |
| 真实摄像头端到端 | ~27-28 FPS（瓶颈在摄像头读帧） |
| Web 虚拟摄像头 (640x480@30) | Stream FPS 12~30（受摄像头帧率与 MJPEG 限制） |
| 图片循环 5 分钟连续 | 平均 61.4 FPS，18,545 帧，零异常（Phase 20） |
| SpatialChecker | 0.03~0.11 ms/帧（可忽略，勿再优化） |
| 显存 | ~216 MiB（nvidia-smi 口径） |

目标口径：**30 FPS 达标 / 45 良好 / 60 优秀**；不承诺所有环境 60 FPS。

## 9. 项目限制

- bbox 目标检测，**非 segmentation**，无像素级盲道区域
- 无三维距离/深度信息；Level 2 是"**疑似占用**"，不是"确认阻挡"
- 盲道未检出时自动降级为 Level 1，不做占用臆测
- 盲道 bbox 为梯形的矩形近似 → 存在表示形式导致的系统性误报源（详见 `docs/spatial_relation_report.md` §19）
- 数据集 blind_road 标注稀疏（test 296/4163 ≈ 7%）
- 仅支持单摄像头、仅本机访问；中文 UI

## 10. 最终测试结果

完整测试矩阵见 `docs/phase21_deployment_report.md` §6（由
`scripts/run_deployment_check.py` 自动生成，日志在 `outputs/phase21_check.log`）。

一句话结论：**23 项检查 PASS=22 / CONDITIONAL=1（真实扬声器）/ FAIL=0 → CONDITIONAL GO**。
