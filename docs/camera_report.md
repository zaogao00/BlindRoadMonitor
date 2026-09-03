# Phase 17 — 实时摄像头检测报告 (Realtime Camera Detection)

> 阶段: Phase 17 — 摄像头 → OpenCV → YOLO(best.pt) → 实时检测画面
> 生成日期: 2026-09-03
> 运行环境: Windows 11 / RTX 5070 Laptop (8 GB) / Python 3.13.14 / torch 2.11.0+cu128 / Ultralytics 8.4.135 / OpenCV 5.0.0 / 项目 `.venv`
> 测试性质: **headless 沙箱验证** (本环境无 GUI/显示器, 且暴露的摄像头为虚拟/回环设备, 非用户物理笔记本摄像头)

---

## 0. 结论速览 (TL;DR)

| 项 | 结果 |
|---|---|
| 模型加载 (best.pt) | ✅ YOLOv8n, 26 类, device=0 |
| 摄像头打开 | ✅ (本沙箱 idx 0 640×480/30fps; 用户机器为物理/USB 摄像头) |
| 连续读帧 | ✅ 80 帧无读取失败 |
| 实时推理 + 绘制 | ✅ 每帧 YOLO + 画框 + 类别 + confidence + FPS |
| 模型推理 FPS (EMA) | **≈ 78.6 FPS** (与 Phase 16 的 88 FPS 一致, 实时余量充足) |
| 端到端循环 FPS (本沙箱) | 12.9 FPS — **被沙箱虚拟摄像头慢速帧抓取(~64ms/帧) 限制, 非模型瓶颈** |
| GPU 峰值显存 | 单帧分配峰值 38.4 MB; 含 CUDA context 实际约 1–2 GB, 远低 8 GB (Phase 16 批量峰值 4.07 GB 已验证安全) |
| CUDA error / OOM | ✅ 无 / 无 |
| 障碍类检测 (真实图) | ✅ car/truck/bus/manhole/guard_rail/trash_bin/plant_pot 等均正常出框 |
| blind_road 检测 | ✅ 能出框 (与 Phase 16 一致, 实例级约 20% 漏检, 远处/小段/遮挡场景) |
| **可见窗口显示** | ⚠️ 本环境无 GUI, 未能渲染 `cv2.imshow` 窗口; 需在用户笔记本运行 `run_camera.py` 本地确认 |
| **物理摄像头实景** | ⚠️ 本沙箱为虚拟/回环摄像头, 真实盲道/障碍场景需在用户物理摄像头确认 |

**判定: Phase 17 链路 PASS (headless 已验证)** — 完整链路「摄像头读帧 → YOLO 推理 → 绘制检测框 + 类别 + confidence + FPS」在本环境跑通, 速度/显存/稳定性均满足实时要求; **唯一的未亲验项是「可见窗口」与「物理摄像头实景」, 二者均因本沙箱无显示器/无物理摄像头, 须由用户在本人笔记本上 `python scripts/run_camera.py --source 0` 确认 (代码已就绪, 不伪造 PASS)。**

---

## 1. 测试环境 (Environment)

| 项 | 值 |
|---|---|
| 操作系统 | Windows 11 家庭版 (10.0.26200) |
| Python | 3.13.14 (venv: `D:\BlindRoadMonitor.venv`) |
| PyTorch | 2.11.0+cu128 |
| CUDA (运行时) | 12.8 (驱动上限 13.1, 未装 Toolkit) |
| Ultralytics | 8.4.135 |
| OpenCV | 5.0.0.93 |
| GPU | NVIDIA GeForce RTX 5070 Laptop GPU, 8 GB (8151 MiB) |
| 模型 | `runs/yolov8n_prod_b32/weights/best.pt` (6.27 MB) |
| 数据配置 | `datasets/processed/data.yaml` (nc=26) |

---

## 2. 摄像头环境 (Camera)

按约束先检查摄像头 (§三):

- 本沙箱通过 `cv2.VideoCapture` 枚举到 **1 个设备: `idx 0`, 640×480, 30 fps**。
- 该设备为沙箱内的**虚拟/回环摄像头** (OpenCV 报 `Camera index out of range` 来自 Orbbec 后端, FFMPEG backend 仍可开), **不是用户的物理笔记本/USB 摄像头**。
- 帧内容实测为变化的中灰画面 (20 帧 mean 111–117, std 60–66 → 真实变化的视频流, 非黑屏), 故可用来验证「读帧 → 推理 → 绘制」整链路, 但**不能代表真实盲道/障碍场景**。
- 用户真实机器: 默认笔记本摄像头或 USB 摄像头, 脚本已做多 backend 回退 (`CAP_DSHOW` / `CAP_MSMF`), 优先 `CAP_DSHOW` (Windows 最稳)。

> 若用户机器无摄像头: 脚本会清晰报错并退出 (exit 3), **不会报项目失败**; 可直接接 USB 摄像头后重跑。

---

## 3. 程序构成 (Deliverables)

| 文件 | 作用 |
|---|---|
| `backend/detector.py` | `Detector` 类: 加载 best.pt + 单帧 YOLO 推理 + OpenCV 绘制 (盲道橙色高亮); 复用沙箱兼容 (YOLO_CONFIG_DIR / MPLCONFIGDIR / ThreadPool monkeypatch / workers=0); 含 CUDA 可用性检查与 warmup; 线程安全 EMA-FPS |
| `backend/camera.py` | 摄像头枚举 `list_cameras()` + 安全打开 `open_camera()` (多 backend 回退, 失败抛清晰 RuntimeError) |
| `scripts/run_camera.py` | 主程序: argparse (`--source/--model/--conf/--imgsz/--device/--no-display/--max-frames/--save-dir/--save-every`); 支持摄像头/视频/单图/目录; q/Q/ESC 退出; 全异常分支处理; 退出释放 `cap.release()` + `destroyAllWindows()` |

推理设置 (§六, 稳定优先): `imgsz=640` / `batch=1` / `device=0` / `workers=0` / `best.pt` / 不重训。`--conf` 默认 0.25, 可按需调低 (盲道漏检偏多, 建议 0.15–0.20)。

---

## 4. 性能测试 (Performance, §七)

### 4.1 模型推理 (真实测试图 + 摄像头帧, 单帧)

| 指标 | 数值 | 说明 |
|---|---|---|
| 模型推理 FPS (EMA) | **78.6 FPS** | 与 Phase 16 单图 88 FPS 一致, 实时余量充足 |
| 单帧推理延迟 | **≈ 12.7 ms** | Phase 16 记录 11.34 ms, 吻合 |
| GPU 峰值显存 (分配) | 38.4 MB | batch=1 单帧; 含 CUDA context 实际约 1–2 GB |
| CUDA error | 无 | — |
| OOM | 无 | — |

### 4.2 端到端实时循环 (本沙箱, idx 0, 80 帧)

| 指标 | 数值 |
|---|---|
| 摄像头 | idx 0, 640×480, 标称 30 fps |
| 处理帧数 | 80 |
| 耗时 | 6.2 s |
| **平均端到端 FPS** | **12.9 FPS** |
| 连续运行 | 稳定, 无卡死/崩溃/读失败 |
| GPU 峰值显存 | 38.4 MB (分配) |

> ⚠️ **重要解读**: 端到端 12.9 FPS 远低于模型推理 78.6 FPS, 差距来自**本沙箱虚拟摄像头的慢速帧抓取 (~64 ms/帧, FFMPEG backend)**, 不是模型瓶颈。用户真实摄像头 (CAP_DSHOW) 读帧通常 <10 ms, 整链路将轻松达到 ≥30 FPS 实时。Phase 16 已确认 GPU 单图 88 FPS、显存 4.07 GB 安全, 实时部署无技术阻碍。

---

## 5. 三类场景验证 (§十)

| 场景 | 验证方式 | 结果 |
|---|---|---|
| A. 空旷/普通场景 | 实时循环每帧检测 + 8 张真实测试图 | ✅ 正常出框, 无异常 |
| B. 含盲道场景 | 5 张含 `blind_road` GT 的测试图推理 | ✅ 能检出 (如 `wotr_20002786` 检出 1 框); 与 Phase 16 一致, 实例级约 20% 漏检 (远/小/遮挡) |
| C. 含障碍物场景 | 真实测试图推理 | ✅ car/truck/bus/manhole/guard_rail/trash_bin/plant_pot 等多类正常出框 |

> 注: B/C 的「真实摄像头实景」确认需在用户物理摄像头完成; 此处用真实数据集图片证明检测能力已具备。

---

## 6. 异常处理 (§八)

脚本显式处理全部要求项, 不裸吞异常:

- 摄像头打不开 → `RuntimeError` + 排查提示, exit 3
- frame 读取失败 → 打印 `[warn]` 并 break (不崩)
- 模型文件不存在 → `FileNotFoundError`, exit 2
- CUDA 不可用 → `RuntimeError`, exit 2
- GPU 推理失败 → `RuntimeError` 包裹原始异常
- OpenCV 窗口异常 → `--no-display` 规避无 GUI 环境
- 用户退出 → q/Q/ESC 或 Ctrl+C, 均 `finally` 释放资源

---

## 7. 测试结果截图 (§九.14)

- `runs/yolov8n_prod_b32/camera_test/img_rod_IMG_19187.jpg` — 单图测试产物 (2 框: car, truck), 证明绘制链路正确。
- 实时循环截图: 本 headless 环境未存 (默认不存连续视频/截图, 遵守 §十二 磁盘安全); 用户本地可加 `--save-every 30 --save-dir <dir>` 存少量测试帧。

---

## 8. 已知问题 (Known Issues)

1. **可见窗口未亲验**: 本沙箱无 GUI/显示器, `cv2.imshow` 无法渲染。需在用户笔记本运行 `python scripts/run_camera.py --source 0` 亲眼确认实时画面 + 检测框。
2. **物理摄像头实景未亲验**: 本沙箱为虚拟/回环摄像头, 真实盲道/障碍场景需用户物理摄像头确认。
3. **blind_road ~20% 实例漏检**: Phase 16 已记录 (R=0.802), 远/小/遮挡/阴影场景易漏。实时阶段建议对 `blind_road` 用更低 `--conf` (0.15–0.20) 并配合告警降级, 避免漏检直接转化为危险。
4. **端到端 FPS 在本沙箱偏低**: 由虚拟摄像头慢速抓取导致, 非模型问题 (见 §4.2)。

---

## 9. 下一阶段建议 (Next Steps)

1. **Phase 18 (候选) — 摄像头告警/语音**: 给盲人用的系统画面叠加无效, 需音频/TTS 提醒; 对 `blind_road` 低置信阈值 + 告警降级; 长尾弱类暂不作高可信事件。
2. **长尾优化**: truck/bus/bicycle/plant_pot/guard_rail 数据增广/过采样/类别加权。
3. **盲道漏检专项**: 收集远距/遮挡/阴影盲道难例补充训练。
4. **部署模型导出 (Phase 17+ 再议)**: 仅当部署端 (边缘/Web) 有需求时导出 ONNX/TensorRT; 本阶段未导出。

---

## 10. 安全与约束遵守 (Safety)

- ✅ 不重新训练; 不修改 `best.pt`; 不重新下载数据集; 不删除 raw/processed/runs 任何文件。
- ✅ 不修改 NVIDIA 驱动 / 不装系统 CUDA Toolkit / 不装 TensorRT / 不导出 ONNX / 不做网页/前端/封装。
- ✅ 不自动进入下一阶段; 本阶段仅产生少量测试截图 (`camera_test/`), 不保存连续视频。
- ✅ 磁盘: 运行前后 D 盘 NORMAL (73.49 GB 剩余), 未触发闸门。
- ✅ 未 push (按用户约束, 仅本地 `git commit "Phase 17: realtime camera detection"`)。

---

## 11. 给用户的一句话总结

> **完整实时链路「摄像头读帧 → YOLO 推理 → 绘制框+类别+conf+FPS」在本环境 headless 跑通: 模型推理 78.6 FPS、单帧 ~12.7 ms、GPU 无错无 OOM、80 帧连续稳定、障碍类与盲道类均正常出框; 端到端 12.9 FPS 受沙箱虚拟摄像头慢速抓取限制而非模型。唯一未亲验的是「可见窗口」与「物理摄像头实景」——请在你的笔记本运行 `python scripts/run_camera.py --source 0` 本地确认。**
