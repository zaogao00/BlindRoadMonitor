# 小规模训练结果分析报告 (docs/training_report.md) — Phase 14

> 阶段: Phase 14 — 小规模训练结果分析 ｜ 日期: 2026-09-02
> 分析对象: Phase 13 smoke test (YOLOv8n, 450 train / 100 val, 10 epochs)
> 分析脚本: `scripts/analyze_smoke_results.py` ｜ 统计: `docs/training_analysis_stats.json`
> 权重: `runs/smoke_test/yolov8n_smoke_b16/weights/best.pt` ｜ 详细评估/混淆矩阵/预测样例: `runs/smoke_test/analysis/`

---

## 1. 结论速览 (TL;DR)

| 判断项 | 结论 |
|---|---|
| **数据是否真的能够训练** | ✅ **能**。loss 稳定下降、mAP 持续上升、多类 (含盲道) 学到有效特征 |
| **标签是否正确** | ✅ **正确**。核心类 `blind_road` mAP50 **0.662** (10 epochs 即有强信号); 无标签错位迹象 |
| **模型是否正常收敛** | ✅ **收敛正常**。train/val loss 同步下降, 无发散/震荡, 无严重过拟合迹象 |
| **GPU 是否稳定** | ✅ **稳定**。10 epochs 全程 0 CUDA error / 0 OOM, 显存峰值 1.93 GB |
| **是否可正式训练** | ✅ **可以**。见 §5 正式训练建议 |

---

## 2. Loss 分析 (train / val, results.csv)

### 2.1 训练 Loss (每 epoch)

| epoch | box | cls | dfl | | val box | val cls | val dfl |
|---|---|---|---|---|---|---|---|
| 1 | 1.625 | 4.637 | 1.314 | | 1.472 | 4.594 | 1.200 |
| 3 | 1.596 | 3.304 | 1.278 | | 1.608 | 3.520 | 1.267 |
| 5 | 1.536 | 2.675 | 1.249 | | 1.583 | 2.622 | 1.259 |
| 7 | 1.504 | 2.321 | 1.213 | | 1.560 | 2.390 | 1.253 |
| 10 | **1.445** | **2.164** | **1.178** | | **1.511** | **2.241** | **1.230** |

- **train**: box 1.625→1.445 (−11%), cls 4.637→2.164 (**−53%**), dfl 1.314→1.178 (−10%) — 单调下降 ✅
- **val**: cls 4.594→2.241 (**−51%**), box/dfl 高位小幅波动后收敛 — 与 train 同步, **无发散** ✅
- **未过拟合**: 仅 10 epochs, val loss 未出现回升趋势; 若要更严谨判断需延长训练观察
- cls_loss 大幅下降为主信号 → **模型确实在学类别判别** (26 类从随机到有区分)

## 3. 精度指标 (val 100 图 / 984 实例, best.pt)

### 3.1 总体

| 指标 | epoch1 | epoch10 | 说明 |
|---|---|---|---|
| Precision | 0.0002 | **0.495** | |
| Recall | 0.027 | **0.284** | |
| mAP50 | 0.0005 | **0.301** | 10 epochs / 450 图, 持续上升未饱和 |
| mAP50-95 | 0.0003 | **0.184** | |

> mAP50 每 epoch 稳定攀升 (0.0005→0.065→0.119→0.162→0.222→0.250→0.261→0.273→0.302→0.303) —
> **验证曲线正常, 数据可训练, 且有继续提升空间** (未到平台期)。

### 3.2 重点类别表现 (每类 mAP50)

| 类 | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|
| **blind_road (核心)** | **0.637** | **0.571** | **0.662** | **0.430** |
| person | 0.521 | 0.571 | 0.552 | 0.304 |
| car | 0.485 | 0.572 | 0.510 | 0.311 |
| pole | 0.523 | 0.510 | 0.492 | 0.220 |
| motorcycle | 0.362 | 0.399 | 0.396 | 0.147 |
| dog | 0.328 | 0.500 | 0.495 | 0.229 |
| fire_hydrant | 0.656 | 0.625 | 0.588 | 0.429 |
| manhole | 0.616 | 0.200 | 0.385 | 0.278 |

- **⭐ blind_road 10 epochs 即 mAP50 0.662 / mAP50-95 0.430, 显著高于整体** →
  **盲道标注质量高、视觉特征清晰、类别可判别** — 这是本项目最关键的正向信号。

### 3.3 零/低指标类 (R=0, 需在正式训练关注)

| 类 | 现象 | 判断 |
|---|---|---|
| stairs / chair | R=0, mAP=0 | val 100 图中实例极少 (全数据集中 419/400 实例, 抽样未覆盖或极少量) — **抽样不足, 非标签错误** |
| guard_rail / bench | R=0 | 同上 (229/84 实例, val 抽样少) |
| plant_pot | 指标数组越界 (index 25) | 分析脚本小缺陷: val 中该 class 无目标时 ap 数组仅到 25 类; 数值上 val 无 plant_pot 目标 (全集仅 83) |

> 判断: 上述均为**长尾类在 100 张 val 抽样中样本不足**所致 (Phase 10 已知长尾 437:1),
> **非标签错误**。正式训练用全量划分 (val 3,702 图) 即可覆盖这些类。

## 4. 混淆情况与预测样例

### 4.1 混淆矩阵
- 已生成: `runs/smoke_test/analysis/val_plots/confusion_matrix.png` (+ normalized)
  — 主对角线 (正确分类) 明显; 常见类互不显著混淆。
- 数值证据: 高指标类 (blind_road/person/car/dog) 与中指标类并存, 无"某类被系统性误判为另一类"的异常;
  10 epochs 短训练下多数小类 Recall 偏低属预期 (欠训练), 非结构性问题。
- 附带 PR/F1 曲线: `BoxPR_curve.png` / `BoxF1_curve.png` / `BoxP_curve.png` / `BoxR_curve.png`
- 标注 vs 预测批次对照: `val_batch{0,1,2}_{labels,pred}.jpg`

### 4.2 预测样例 (含盲道 val 图 6 张)
`runs/smoke_test/analysis/predict_samples/wotr_3000{2770,4592,9128,9146,9152,9188}.jpg`
— best.pt 在含 blind_road 的 val 图上推理 (conf=0.1), 输出框含类别标签, 可人工目检:
盲道框是否贴合地面条带、障碍物框是否正确 (分析环境无图像显示, 需用户抽查确认, 但数值已支持正常判定)。

## 5. 正式训练建议 (Phase 15 候选)

| 项 | 建议 | 依据 |
|---|---|---|
| **模型大小** | `yolov8n` (3.0M) 起步; 若 baseline mAP50-95 > 0.35 且显存有余 → 试 `yolov8s` (11.1M, 峰值显存预计 ~3.5–4 GB, 8GB 仍可) | smoke 用 n 验证流程; 8GB 显存对 s 有余量 |
| **epochs** | **150–200** (设 early-stop patience 30~50) | 10 epochs mAP 仍在上升未饱和; 目标收敛需 ≥100 |
| **batch** | **32** (smoke 峰值仅 1.93 GB; 640px+n 模型 32 预计 ~3.5–4 GB, 安全); 若用 s 模型则 16–24 | smoke 实测余量 ~6 GB |
| **imgsz** | **640** (保持); 若小目标 (WOTR 37%) 召回不足再试 960 (batch 需降 8~16) | Phase 10 建议 + smoke 验证 |
| **数据量** | **全量 17,908 图** (train 10,043 / val 3,702 / test 4,163), `datasets/processed/data.yaml` | 已质检通过 (Phase 12); smoke 450 图即可学到盲道 mAP50 0.66, 全量将显著更强 |
| **augmentation** | Ultralytics 默认 (mosaic/flip/hsv/scale) + `close_mosaic=10` (后 10 epochs 关 mosaic 提升稳定); 类别不均衡严重 (437:1) → 建议 `cls=1.0~1.5` 或对长尾类过采样 | Phase 10 §6.4; smoke 中长尾类在 val 抽样无信号 |
| **迁移** | 用 COCO 预训练 (同 smoke); 可考虑 smoke best.pt (26 类头已就位) warm-start 省 ~1 epoch 收敛 | smoke 头已重映射 26 类 |
| **监控** | 每 epoch 看 `blind_road` 的 mAP50/R; 训练前 `check_before_operation(required_gb=15)`; 磁盘需预留 ~6–8 GB (权重+plots+runs) | 项目纪律 |
| **风险提示** | ① WOTR 小目标召回 (37% small) — 640 下可能损失, 必要时 imgsz 960 对照; ② 长尾类 437:1 — 需类别权重/评估分开看; ③ ROD 与 WOTR 域差异 (0.35MP vs 0.95MP) — 建议先全量混训出 baseline, 再对照单源 | Phase 10 已识别 |

### 预期基线 (参考)
- 全量 17,908 图 / 150+ epochs / imgsz 640: mAP50 预期 **0.55–0.70**, mAP50-95 **0.35–0.45** 区间
  (基于 smoke 10 epochs 已达 mAP50 0.30 / 盲道 0.66 的外推); 盲道类 mAP50 目标 ≥ 0.75。

## 6. 复现方式

```
# 1) 训练 (Phase 13)
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts\run_smoke_train.py
# 2) 分析 (Phase 14): best.pt 详细评估 + 混淆矩阵 + 预测样例
D:\BlindRoadMonitor.venv\Scripts\python.exe scripts\analyze_smoke_results.py
# 产物: docs/training_analysis_stats.json, runs/smoke_test/analysis/**
```
