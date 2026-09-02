# 小规模 YOLO 训练验证报告 (docs/training_smoke_test.md) — Phase 13

> 阶段: Phase 13 — 小规模 YOLO 训练验证 (Smoke Test) ｜ 日期: 2026-09-02
> 运行脚本: `scripts/run_smoke_train.py` ｜ 子集构建: `scripts/make_smoke_subset.py`
> 统计 JSON: `docs/training_smoke_test_stats.json` ｜ 权重: `runs/smoke_test/yolov8n_smoke_b16/weights/{best,last}.pt`
> 任务: detection ｜ 模型: **YOLOv8n** (COCO 预训练迁移) ｜ 类别: **26** (核心 `blind_road`)

---

## 1. 训练配置

| 项 | 值 |
|---|---|
| 数据 | `datasets/smoke_test/` — train **450** 图 (含盲道 74) / val **100** 图 (含盲道 18) (126 MB) |
| 模型 | `models/yolov8n.pt` 预训练 → 覆盖 nc=80→26 (Remapped 9/26 类别头, Transferred 322/355) |
| imgsz | **640** |
| batch | **16** (RTX 5070 8GB, 无 OOM, 未触发降级) |
| AMP | **开启** (Automatic Mixed Precision checks passed) |
| epochs | **10** (29 iter/epoch) |
| 优化器 | AdamW (auto, lr≈0.00033) |
| workers | 0 (沙箱限制 dataloader 子进程/管道, 见 §5) |
| 种子 | 20260902 |

## 2. 验证目标达成情况 (全部 ✅)

| 目标 | 结果 |
|---|---|
| 数据读取正常 | ✅ 450 train / 100 val 扫描成功 (0 corrupt, 0 missing) |
| 标签正常 | ✅ 标签缓存创建成功, 类别头正确重映射 |
| 模型正常 | ✅ 网络构建 130 层 / 3,015,918 参数 / 8.2 GFLOPs, 前向反向无错误 |
| GPU 正常 | ✅ CUDA:0 RTX 5070, AMP 检查通过, 全程无 CUDA error |
| **loss 正常下降** | ✅ box 1.62→**1.45**, cls 4.64→**2.16**, dfl 1.31→**1.18** (10 epochs) |
| 验证流程正常 | ✅ 每 epoch 结束 val 评估 + 结束时 best.pt 独立验证, 输出 P/R/mAP |

## 3. 关键指标记录

### 3.1 时间与显存

| 项 | 值 |
|---|---|
| 总训练时间 | **103.4 s** (0.027 h; 10 epochs ≈ 9.6 s/epoch) |
| GPU 显存峰值 (allocated) | **1,931.6 MB** (≈1.9 GB / 8 GB, 余量充足) |
| GPU 显存 (训练表) | 2.5 G 稳定 (含缓存) |
| 峰值显存安全余量 | ~6 GB → batch 可升至 32~48 (本测试不追求, 保持 16) |

### 3.2 Loss 曲线 (train, epoch 1 → 10)

| epoch | box_loss | cls_loss | dfl_loss | mAP50 | mAP50-95 | P | R |
|---|---|---|---|---|---|---|---|
| 1 | 1.625 | 4.637 | 1.314 | 0.0005 | 0.0003 | 0.0002 | 0.027 |
| 3 | 1.584 | 3.188 | 1.262 | 0.119 | 0.077 | 0.676 | 0.085 |
| 6 | 1.505 | 2.436 | 1.216 | 0.250 | 0.154 | 0.512 | 0.238 |
| 8 | 1.479 | 2.235 | 1.193 | 0.273 | 0.176 | 0.519 | 0.274 |
| 10 | **1.445** | **2.164** | **1.178** | **0.303** | **0.185** | **0.497** | **0.293** |

- **Loss 全程单调下降趋势** ✅ (验证"loss 正常下降")
- mAP50 0.0005 → **0.303**、mAP50-95 0.185 (10 epochs / 450 图, 不追求精度, 仅证流程)
- val 最终: box 1.511 / cls 2.241 / dfl 1.230

### 3.3 错误记录

| 项 | 结果 |
|---|---|
| CUDA OOM | **无** (batch 16 全程稳定) |
| CUDA error / driver error | **无** |
| 训练中断 | **无** (exit code 0) |
| 数据加载错误 | 无 (仅 1 个 JPEG 警告: `wotr_10006682.jpg` 轻微损坏, Ultralytics 自动修复后继续 — 修复写回 smoke_test 子集, **不影响 raw/processed**) |

## 4. 产物

- `runs/smoke_test/yolov8n_smoke_b16/weights/best.pt` (6.2 MB) — best 权重 (mAP50 0.303)
- `runs/smoke_test/yolov8n_smoke_b16/weights/last.pt` (6.2 MB)
- `runs/smoke_test/yolov8n_smoke_b16/results.csv` — 逐 epoch 全量指标

## 5. 实施中解决的环境问题 (沙箱适配, 非模型问题)

1. **字体下载失败**: Ultralytics 首次运行尝试下载 Arial.ttf 至 `%APPDATA%` (不可写 + curl schannel 不可用)。
   解决: 设置 `YOLO_CONFIG_DIR=D:\BlindRoadMonitor\.yolo_config` (重定向配置/字体目录至工作区), 预置系统 Arial.ttf;
   同时设 `MPLCONFIGDIR` 至工作区规避 matplotlib 缓存写入失败。
2. **标签缓存扫描 [WinError 5]**: Ultralytics 用 `multiprocessing.pool.ThreadPool` (内部 SimpleQueue 创建**命名管道**,
   被沙箱拒绝)。解决: 在 `run_smoke_train.py` 内 monkeypatch 为 `concurrent.futures.ThreadPoolExecutor` 包装
   (纯线程, 无管道; 仅影响缓存扫描, 不改训练逻辑)。
3. **dataloader workers=0**: Windows 下 worker 子进程走 spawn + 管道, 沙箱受限 → 设 0 (450 图单进程足够快)。

## 6. 结论

- **Smoke test 全部通过**: 数据 / 标签 / 模型 / GPU / loss 下降 / 验证流程 均正常。
- 无 CUDA OOM、无 CUDA error; batch=16 + imgsz=640 + AMP 在 RTX 5070 8GB 上**余量充足** (峰值 1.9 GB)。
- 10 epochs / 450 图 / 103 秒 / mAP50 0.303 — 仅为流程验证数值, **不代表最终精度**。
- **下一步 (Phase 14 候选)**: 全量数据集 (17,908 图) 正式训练 — 可保持 batch 16 (或按显存升 24~32),
  epochs 100~200, 评估各 (尤其 `blind_road` 核心类) mAP; smoke 权重可作 warm-start 参考。

## 7. 复现方式

```
# 1) 构建子集 (450 train + 100 val, 含盲道优先)
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts\make_smoke_subset.py
# 2) 训练 10 epochs (脚本内已含沙箱适配)
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts\run_smoke_train.py
```
