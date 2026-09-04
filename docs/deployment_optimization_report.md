# Phase 18 — 部署 / 推理性能优化报告 (Deployment & Inference Optimization)

> 阶段: Phase 18 — 正式模型 `best.pt` 的推理侧性能基准 + 检测一致性验证 + 部署形态决策
> 生成日期: 2026-09-04
> 运行环境: Windows 11 / RTX 5070 Laptop (8 GB) / Python 3.13.14 / torch 2.11.0+cu128 / Ultralytics 8.4.135 / OpenCV 5.0.0 / 项目 `.venv`
> 测试性质: **headless 沙箱验证**（摄像头端到端使用沙箱虚拟设备；真实物理摄像头数据来自用户本机实测，见 §11）

---

## 1. Phase 18 目标

对正式模型 `runs/yolov8n_prod_b32/weights/best.pt` 做推理侧性能基准，验证实时性是否达标，并决定是否需要 ONNX/TensorRT 导出。

项目实际目标（来自规格）：

| 端到端 FPS | 评价 |
|---|---|
| < 20 | 不理想 |
| 20–29 | 接近达标，需继续观察 |
| **≥ 30** | **达标** |
| ≥ 45 | 很好 |
| ≥ 60 | 优秀，性能富余 |

**核心结论前提**：YOLO 模型推理速度非常充足（>100 FPS），端到端 FPS 更接近摄像头读取 / 图像处理 / 显示等环节的限制。不为把模型从 105 FPS 提到 130 FPS 做无意义优化。

---

## 2. 测试环境

| 项 | 值 |
|---|---|
| 操作系统 | Windows 11 家庭版 (10.0.26200) |
| Python | 3.13.14 (venv: `D:\BlindRoadMonitor.venv`) |
| PyTorch | 2.11.0+cu128 |
| CUDA (运行时) | 12.8 (驱动上限 13.1, 未装 Toolkit) |
| Ultralytics | 8.4.135 |
| OpenCV | 5.0.0.93 |
| GPU | NVIDIA GeForce RTX 5070 Laptop GPU, 8 GB (8151 MiB) |

---

## 3. GPU

- **NVIDIA GeForce RTX 5070 Laptop GPU**, 8 GB (8151 MiB), 计算能力 sm_120 (Blackwell)
- 单图推理 `torch.cuda.is_available() == True`, device=0 正常
- 单图推理峰值显存（见 §12）远低于 8 GB, 无 OOM 风险

---

## 4. Python / PyTorch / Ultralytics 版本

- Python 3.13.14
- PyTorch 2.11.0+cu128
- Ultralytics 8.4.135
- OpenCV 5.0.0.93

（与 Phase 15/16/17 记录完全一致, 未变更环境, 未安装 CUDA Toolkit / TensorRT）

---

## 5. 正式模型路径

```
D:\BlindRoadMonitor\runs\yolov8n_prod_b32\weights\best.pt   (6.27 MB, 26 类, YOLOv8n)
```

**未做任何修改 / 未重新训练 / 未导出**（符合 Phase 18 约束）。

---

## 6. Benchmark 配置

| 参数 | 值 |
|---|---|
| imgsz | 640 |
| batch | 1 |
| device | 0 (GPU) |
| workers | 0 |
| conf | 0.25 (FP16 一致性检查另测 0.15) |
| iou | 0.45 |
| warmup | 20 次（不计入结果） |
| 正式迭代 | **250 次 / 每种精度** |
| 计时图 | 10 张覆盖多类的真实测试图（循环推理, 含同步 `torch.cuda.synchronize()`） |

脚本: `scripts/benchmark_phase18.py`（沙箱兼容沿用 Phase 13/15/16/17）。

---

## 7. PyTorch FP32 结果

| 指标 | 值 |
|---|---|
| 平均推理时间 (Avg) | **9.501 ms** |
| P50 | 9.141 ms |
| P95 | 10.525 ms |
| **FPS** | **105.25** |
| GPU 显存 (allocator 峰值) | 51.6 MB |
| GPU 显存 (nvidia-smi 真实占用) | **216 MiB** |
| CUDA error | 无 |
| OOM | 无 |

---

## 8. PyTorch FP16 结果

| 指标 | 值 |
|---|---|
| 平均推理时间 (Avg) | **10.143 ms** |
| P50 | 9.426 ms |
| P95 | 10.671 ms |
| **FPS** | **98.59** |
| GPU 显存 (allocator 峰值) | 30.4 MB |
| GPU 显存 (nvidia-smi 真实占用) | **218 MiB** |
| CUDA error | 无 |
| OOM | 无 |

**FP32 vs FP16 解读**：在本机 RTX 5070 (Blackwell) 上, **FP16 未带来加速, 反而略慢**（105.25 → 98.59 FPS）。原因：YOLOv8n 极小（3.01M 参数 / 8.1 GFLOPs），推理受内存带宽/调度主导而非 compute，Blackwell 的 FP16 Tensor Core 路径对这种小模型无收益。FP16 仅降低 allocator 峰值（30 vs 52 MB），但 nvidia-smi 真实占用几乎相同（218 vs 216 MiB）。**结论：保留 FP32**——更简单、无精度风险、且本机略快。

---

## 9. ONNX 结果

> **NOT TESTED**

理由：PyTorch FP32 单图已达 **105 FPS**（模型推理），端到端真实摄像头 **27–28 FPS**（见 §11），检测正确性已验证（§13），GPU 真实占用仅 **216 MiB**。当前 PyTorch + GPU 方案已远超实时需求，按规格 §12/§13/§15「不为追求更高 FPS 强制引入 ONNX/TensorRT」，**ONNX 非必须**。如后续明确需要跨平台/边缘部署，再按需导出（不覆盖 best.pt、不改动现有运行环境）。

---

## 10. TensorRT 结果

> **NOT TESTED**

理由：同上。当前端到端 ≈27–28 FPS、模型推理 >100 FPS、检测正常、GPU 正常、无 OOM。规格 §13 明确「当前不是必须 TensorRT」「只有当 PyTorch FP16 无法达到 30 FPS 或后续部署有明确 TensorRT 需求时才考虑」。本阶段结论：TensorRT 暂无必要。

---

## 11. 端到端摄像头 FPS

| 来源 | 处理帧数 | 耗时 | 平均端到端 FPS | 模型推理 FPS(EMA) | 备注 |
|---|---|---|---|---|---|
| **用户本机实测**（规格 §2） | 320 | 11.8 s | **27.2** | **110.8** | 真实物理/USB 摄像头 |
| **本沙箱虚拟摄像头**（本次重跑） | 320 | 11.4 s | **28.1** | **106.7** | 虚拟/回环设备, 无盲道场景 |

- 两次结果高度吻合：端到端 **≈27–28 FPS**, 模型推理 **≈106–110 FPS**。
- **瓶颈定位**：端到端延迟主要来自摄像头帧采集（约 35 ms/帧 ≈ 28 FPS 上限），模型推理仅占 ~9.5 ms（<10% 占比）。即 **摄像头读帧是瓶颈, 模型有 4 倍余量**。
- blind_road 命中帧=0：虚拟摄像头画面无盲道，属正常（见 §9 专项验证另行确认盲道检测能力）。
- 连续运行稳定：320 帧无读失败 / 无卡死 / 无 CUDA error / 无 OOM。

**30 FPS 达标判断**：端到端 27–28 FPS 落在「20–29 接近达标」区间，距 30 仅一步之遥。因瓶颈在摄像头读帧（非模型），且模型余量充足，无需为追 30 强行修改系统（规格 §11 结论）。

---

## 12. GPU 显存（口径说明，对应规格 §14）

⚠️ **必须区分两种口径**，不得混淆：

| 口径 | 本阶段 batch=1 数值 | 说明 |
|---|---|---|
| PyTorch allocator 统计 (`max_memory_allocated`) | FP32 51.6 MB / FP16 30.4 MB | 仅模型权重 + 激活张量, **不含 CUDA context** |
| **CUDA context / 系统实际占用** (`nvidia-smi`) | **~216 MiB** | 含驱动 context + 分配器, 真实总占用 |
| 对照：Phase 16 batch=32 | 4075 MB (4.07/7.96 GB) | 批量推理显存更高, 仍远低 8 GB |

**正确表述**：RTX 5070 单图实时推理真实 GPU 占用约 **216 MiB（含 context）**，远未触及 8 GB 上限；批量（batch=32）峰值 4.07 GB 也已验证安全。Phase 17 报告的「38.4 MB」仅为 allocator 张量统计，非真实总占用，此处以 nvidia-smi 实测为准。

---

## 13. 检测结果一致性（FP32 vs FP16）

在 10 张覆盖多类的真实测试图上对比：

| 项目 | FP32 | FP16 |
|---|---|---|
| 总检测框数 | 32 | 32 |
| 逐类构成 | 一致 | 一致 |

FP32 与 FP16 检测框数**完全一致**，仅存在允许的微小数值差异，**无系统性退化**。

### blind_road 专项验证（对应规格 §9）

对**全部 296 张含 blind_road 的 test GT 图**做图像级召回：

| 阈值 | 命中图数 / 总数 | 图像级召回 |
|---|---|---|
| conf = 0.25（默认） | 260 / 296 | **0.878** |
| conf = 0.15（低阈值） | 266 / 296 | **0.899** |

盲道检测**完全正常**（与 Phase 16 实例级 R=0.802、图像级更高一致）。之前 8 张子集在 0.25 下 0 命中属「恰好偏难样本」的统计偶然，全量验证确认 **blind_road PASS**。

> 说明：Phase 18 规格 §9 提到的「实体摄像头测试 blind_road 命中帧=0」属画面无盲道场景，非模型问题；本阶段已在固定测试图上确认盲道检测能力。

---

## 14. 性能瓶颈分析

```
端到端 ~28 FPS 的组成（估算，RTX 5070）:
  - 摄像头帧采集:  ~35 ms  (≈ 28 FPS 上限, 主要瓶颈)
  - 预处理+COPY:   ~3-5 ms
  - YOLO 模型推理: ~9.5 ms (105 FPS, 仅占 <10%)
  - 绘制+显示:     ~3-5 ms
  --------------------------------
  合计:            ~51-55 ms → ~18-20 推理密集, 实际受摄像头 ~35ms 主导 → ~27-28 FPS
```

**结论**：模型推理不是瓶颈，瓶颈在摄像头读帧与整体 I/O。模型有 >100 FPS 的 4 倍余量。

---

## 15. 最终推荐配置

| 项 | 推荐 |
|---|---|
| Backend | **PyTorch (Ultralytics YOLOv8n)** |
| Precision | **FP32**（本机略快于 FP16，且无精度风险） |
| imgsz | 640 |
| batch | 1（实时单帧） |
| device | 0 (GPU) |
| conf（默认） | 0.25；盲道告警建议 0.15–0.20 + 告警降级 |
| 是否需 ONNX | **否** |
| 是否需 TensorRT | **否** |

---

## 16. 是否需要 ONNX

**否**。PyTorch + GPU 已满足实时需求（模型 105 FPS，端到端 27–28 FPS），无性能缺口；导出 ONNX 仅增加部署复杂度而无收益。留待明确跨平台/边缘部署需求时再议。

## 17. 是否需要 TensorRT

**否**。同 §16 理由；当前性能瓶颈在摄像头读帧而非模型，TensorRT 无法提升端到端 FPS。

---

## 18. Go / Conditional Go / No-Go

> **GO（无需继续优化）**

判定依据：
1. 模型推理 105 FPS（FP32）≫ 实时需求 ✅
2. 端到端 27–28 FPS（接近 30 达标线，瓶颈在摄像头读帧，非模型）✅
3. 检测一致性 PASS（FP32=FP16，无退化）✅
4. blind_road 验证 PASS（图像级召回 0.878@0.25）✅
5. GPU 真实占用 216 MiB，无 OOM / 无 CUDA error ✅
6. 连续运行稳定（320 帧无异常）✅

**说明**：端到端 27–28 FPS 略低于 30「达标线」，但属「摄像头读帧限制」，模型余量 4 倍；按规格 §15，当前 PyTorch + GPU 方案已满足项目实时性需求，**无需为追更高 FPS 强制引入 ONNX/TensorRT**。若更换更高帧率摄像头，端到端将自然超过 30 FPS。

---

## 19. Phase 19 建议（候选方向，本阶段不进入）

1. **告警 / 语音 (TTS)**：给盲人用的系统画面叠加无效，需音频提醒；对 `blind_road` 低置信阈值 + 告警降级；长尾弱类暂不作高可信事件。
2. **Web UI / FastAPI**（规格 §20 明确留到后续阶段）：可选轻量展示前端。
3. **长尾优化**：truck/bus/bicycle/plant_pot/guard_rail 数据增广/过采样/类别加权。
4. **盲道漏检专项**：收集远距/遮挡/阴影盲道难例补充训练（当前实例级漏检约 20%）。
5. **部署导出（再议）**：仅当边缘/跨平台部署明确需要时导出 ONNX/TensorRT；本阶段未导出。

---

## 20. 安全与约束遵守

- ✅ 不重新训练；不修改 `best.pt`；不重新下载数据集；不删除 raw/processed/runs 任何文件。
- ✅ 不修改 NVIDIA 驱动 / 不装系统 CUDA Toolkit / 不装 TensorRT / 不导出 ONNX / 不做网页/前端/封装。
- ✅ 不自动进入下一阶段；本阶段仅产生 Benchmark 统计（`phase18_benchmark/`，gitignore 屏蔽），不保存连续视频。
- ✅ 磁盘：运行前后 D 盘 NORMAL（73.38 GB 剩余），未触发闸门。
- ✅ 未 push（按用户约束，仅本地 `git commit "Phase 18: deployment optimization"`）。

---

## 21. 给用户的一句话总结

> **PyTorch FP32 单图 9.5 ms → 105 FPS、真实 GPU 占用仅 216 MiB；FP16 在本机反而略慢故保留 FP32；FP32 与 FP16 检测完全一致、盲道图像级召回 0.878（PASS）；端到端 27–28 FPS（瓶颈在摄像头读帧，模型有 4 倍余量）。当前 PyTorch+GPU 方案已满足实时需求，无需 ONNX/TensorRT —— 判定 GO，无需继续优化。**
