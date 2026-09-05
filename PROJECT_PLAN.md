# PROJECT_PLAN.md — 基于 YOLO 的智能盲道障碍物监测与预警系统

> 本文件是项目总规划与阶段台账。每一阶段的详细结论见对应报告（`docs/`）与
> `PROJECT_STATUS.md` / `CHANGELOG.md`。
>
> 当前阶段：**Phase 21 — 最终打包与部署（COMPLETE / CONDITIONAL GO）**
> **Phase 21 之后不自行进入 Phase 22，等待下一步指令。**

---

## 一、总体目标

构建一个可在 Windows 11 + NVIDIA 笔记本 GPU 上实时运行的系统：

```text
摄像头 → YOLO 检测 → 盲道识别 + 障碍物识别
       → 二维空间关系判断（是否疑似占用盲道）
       → 分级预警（Level 0/1/2）
       → Web UI 可视提醒 + TTS 语音提醒
```

设计原则：**简单、可解释、稳定、实时**。不追求论文级算法，不引入额外 AI 模型，
不做 segmentation（数据无 mask 监督）。

## 二、技术选型（已锁定，不再更换）

| 层次 | 选型 |
| ---- | ---- |
| 检测模型 | YOLOv8n（`runs/yolov8n_prod_b32/weights/best.pt`，26 类） |
| 训练/推理 | PyTorch 2.11.0+cu128 + Ultralytics 8.4.135，FP32 |
| 图像 | OpenCV 5.0.0.93 |
| Web | FastAPI + uvicorn + MJPEG（原生 HTML/CSS/JS，无前端构建） |
| 语音 | pyttsx3（Windows SAPI 本机语音，无大模型、无联网） |
| 部署 | Python venv + `scripts\start_web.bat`（**不做 EXE**） |

**明确不引入**：CUDA Toolkit、TensorRT、ONNX Runtime、分割模型、姿态/深度模型、
大型 TTS 模型、React/Vue 等前端框架。

## 三、阶段台账

| Phase | 内容 | 状态 | 关键结果 |
| ----- | ---- | ---- | -------- |
| 00 | 项目安全与磁盘管理初始化 | ✅ | 磁盘闸门 `check_before_operation()` |
| 02 | 开发环境检查 | ✅ | Windows 11 / RTX 5070 / 驱动 591.86 |
| 03 | 隔离 Python 虚拟环境 | ✅ | `D:\BlindRoadMonitor.venv` |
| 04 | PyTorch GPU 环境 | ✅ | torch 2.11.0+cu128 |
| 05 | RTX 5070 GPU 验证 | ✅ | CUDA 可用，无 CUDA Toolkit |
| 06 | Ultralytics 环境 | ✅ | 8.4.135 |
| 07 | YOLO 基础推理验证 | ✅ | |
| 08 | 公开盲道数据集调研 | ✅ | WOTR + ROD |
| 09 | 数据集安全下载 | ✅ | 只读原始目录 |
| 10 | 数据集结构与标签分析 | ✅ | |
| 11 | YOLO 数据集转换 | ✅ | 17,908 图 / 195,719 实例 / 26 类 |
| 12 | 可视化质量检查 | ✅ | 120 张全部正常 |
| 13 | 小规模训练验证 | ✅ | mAP50 0.301 |
| 14 | 小规模训练结果分析 | ✅ | 盲道 mAP50 0.662 |
| 15 | 全量正式训练 | ✅ | test mAP50 **0.776** / 盲道 **0.849** |
| 16 | 推理验证 | ✅ | GPU 88 FPS，显存 4.07 GB |
| 17 | 实时摄像头检测 | ✅ | headless 链路 PASS（实景待用户确认） |
| 18 | 部署 / 推理性能优化 | ✅ | FP32 105 FPS；FP16 不更快 → 保留 FP32；无需 ONNX/TensorRT |
| 19 | Web UI + 障碍物实时提醒 | ✅ | MJPEG + 视觉横幅 + 异步 TTS（冷却 2.5s） |
| 20 | 障碍物是否占用盲道（空间关系） | ✅ GO | IoU+中心+交叠比三条件；阈值 3×3 扫描；单元测试 10/10；误报可归因 0 |
| 21 | 最终打包与部署 | ✅ CONDITIONAL GO | venv + `start_web.bat`；部署测试 20 项；**不做 EXE** |

## 四、Phase 21 的部署形态（最终决定）

- **部署方式**：`venv + scripts\start_web.bat`（不是 EXE）。
- **不做 EXE 的理由**：PyInstaller 需把 PyTorch CUDA 运行时、Ultralytics、OpenCV、
  SAPI 相关依赖一并打包，体积预计 2~4 GB，且摄像头 / GPU / TTS 的兼容性风险高，
  收益（双击即用）已被 `start_web.bat` 覆盖。除非后续明确要求，否则维持现状。
- **访问方式**：`http://127.0.0.1:8000`，仅本机，不对外网开放。

## 五、待用户实机确认（沙箱不能替代）

1. **真实扬声器语音播报**（Level 1 / Level 2 文案与冷却节奏）
2. **可见窗口与物理摄像头实景**（沙箱为虚拟摄像头，且无 GUI）
3. Windows 11 实机上双击 `scripts\start_web.bat` 的一键启动体验

## 六、后续可选方向（**未启动，等待指令**）

- 盲道分割（segmentation / 多边形标注）以根治"梯形 bbox 矩形近似"的系统性误报
- 多摄像头 / 视频文件批量分析
- 告警记录与回放
- 现场可调阈值面板（把 IoU / 交叠 / 中心护栏暴露到 UI）

以上均**不属于 Phase 21**，未经指示不得自行开始。
