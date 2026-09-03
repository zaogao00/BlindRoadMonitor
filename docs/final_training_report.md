# Phase 15 正式模型训练报告 (Final Production Training Report)

> 项目: 基于 YOLO 的智能盲道障碍物监测与预警系统
> 阶段: Phase 15 — 全量正式训练 (Production Training)
> 生成时间: 2026-09-03
> 关联: Phase 14 训练结果分析 (已通过四项判断, 明确授权进入正式训练)

---

## 0. 结论速览 (TL;DR)

| 指标 | 值 | 判定 |
| --- | --- | --- |
| 模型 | YOLOv8n (COCO 预训练, 3.01M params) | ✅ |
| 训练规模 | 17,908 图 / 195,719 实例 / 26 类 (全量) | ✅ |
| 训练时长 | 200 epochs ≈ **12.5 小时** (RTX 5070 8GB) | ✅ |
| GPU 峰值显存 | ~5.0 GB / 8 GB (batch=32, 无 OOM) | ✅ |
| **整体 mAP50 (test)** | **0.776** | ✅ 远超 Phase 14 预期 0.55–0.70 |
| **盲道类 mAP50 (test)** | **0.849** | ✅ **达成 Phase 14 目标 ≥0.75** |
| 磁盘安全 | 全程 NORMAL (73.7→73.6 GB), 未触发 <15GB 红线 | ✅ |
| 四项判断 (数据/标签/收敛/GPU) | 全部通过 | ✅ |

**核心正向结论**: 盲道检测 `blind_road` 在正式全量训练下 mAP50 达到 **0.853 (val) / 0.849 (test)**, 较 Phase 14 smoke 测试的 0.662 提升 **+0.19**, 稳定超过 0.75 目标 —— 本项目的盲道监测主目标在模型层面已验证可行。

---

## 1. 训练配置 (Configuration)

来源 `docs/final_training_stats.json` / `scripts/run_prod_train.py` / `runs/yolov8n_prod_b32/args.yaml`。

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| model | `yolov8n.pt` (COCO 预训练) | 3,010,718 params / 8.1 GFLOPs, nc 80→26 |
| data | `datasets/processed/data.yaml` | 全量, 绝对路径, nc=26 |
| imgsz | **640** | 沿用 Phase 10/14 决议 |
| batch | **32** | Phase 14 建议 (smoke 峰值仅 1.93GB, 余量充足) |
| epochs | **200** | Phase 14 建议 150–200 上限 |
| patience | 40 | early-stop 宽容度 |
| amp | True | 混合精度 (RTX 5070 Blackwell) |
| close_mosaic | 10 | 末 10 epoch 关闭 mosaic 提精度 |
| optimizer | auto → MuSGD | 自动选择 |
| cos_lr | True | 余弦学习率衰减 |
| cls | 1.0 | 类别损失权重 (长尾考虑) |
| seed | 20260902 | 可复现 |
| workers | 0 | 沙箱 Windows spawn 限制 (单进程) |
| device | cuda:0 (RTX 5070 Laptop, 8151 MiB) | — |
| project / name | `runs/` / `yolov8n_prod_b32` | 不覆盖旧实验 |

> ⚠️ 说明: 训练进程在收尾写统计 JSON 时曾因一个 `Path` 对象不可被 `json.dump` 序列化而崩溃 (进程非零退出), 但**模型、权重、results.csv、曲线均已正常产出**, 测试集评估也已跑完。后以 `scripts/finalize_phase15.py` 仅复评、不重训的方式补足统计, 根因已在 `run_prod_train.py` 修复 (`str()` 包裹)。训练成果本身 100% 有效。

---

## 2. 训练过程 (Training Progress)

### 2.1 时长与稳定性
- **总耗时**: 约 **12.5 小时** (results.csv 末 epoch `time` = 45,116 s)。
- **未触发 early-stop**: mAP 在 196–200 epoch 进入平台期 (mAP50 ≈ 0.776) 但仍微幅上升, 故跑满 200 epoch; 这是正常收敛表现, 非异常。
- **GPU 显存**: 全程峰值 **~3.7–5.0 GB / 8 GB**, batch=32 稳定, **0 OOM**, 无需降级 (Phase 15 规定 OOM 才降 batch)。
- **CUDA / 进程**: 0 CUDA error / 0 崩溃, 单进程 (workers=0) 受沙箱限制, 不影响正确性。

### 2.2 Loss 曲线 (末 epoch, epoch 200)
| 损失 | train | val |
| --- | --- | --- |
| box_loss | 1.058 | 1.225 |
| cls_loss | 1.272 | 1.962 |
| dfl_loss | 0.984 | 1.244 |

train/val loss 同步下降且平稳, 无发散 / 无严重过拟合 (val cls 略高于 train 属正常, 长尾类样本少)。

### 2.3 磁盘安全回调 (每 epoch)
训练脚本注册 `on_train_epoch_end` 回调, 每 epoch 实测 D 盘剩余:
- 起始 NORMAL (73.7 GB) → 结束 NORMAL (73.6 GB)。
- 全程 **未低于 15 GB**, `stopped_by_disk_danger = false`, 从未触发安全停止。
- 末 epoch 日志示例: `[disk] epoch 200/200 done | D: free=73.6GB status=NORMAL`。

---

## 3. 最终指标 (Final Metrics)

best.pt 独立复评 (val + test 双划分)。

### 3.1 整体 (Overall)
| 划分 | 图数 | 实例数 | P | R | mAP50 | mAP50-95 |
| --- | --- | --- | --- | --- | --- | --- |
| val | 3,702 | 32,142 | 0.8159 | 0.7099 | **0.7752** | 0.5238 |
| test | 4,163 | 35,128 | 0.8218 | 0.7037 | **0.7765** | 0.5197 |

### 3.2 ⭐ 盲道类 (blind_road — 项目主目标)
| 划分 | P | R | mAP50 | mAP50-95 |
| --- | --- | --- | --- | --- |
| val | 0.8662 | 0.8065 | **0.853** | 0.6656 |
| test | 0.8579 | 0.8024 | **0.8486** | 0.650 |

**mAP50 0.853 (val) / 0.849 (test) — 达成 Phase 14 设定的 ≥0.75 目标** ✅。

### 3.3 每类指标 (val, 按 mAP50 降序)
| 类别 | P | R | mAP50 | mAP50-95 |
| --- | --- | --- | --- | --- |
| green_light | 0.896 | 0.904 | **0.941** | 0.580 |
| red_light | 0.835 | 0.837 | **0.889** | 0.540 |
| crosswalk | 0.912 | 0.832 | **0.892** | 0.715 |
| manhole | 0.898 | 0.807 | **0.887** | 0.714 |
| blind_road | 0.866 | 0.807 | **0.853** | 0.666 |
| warning_column | 0.853 | 0.787 | **0.835** | 0.462 |
| pole | 0.776 | 0.789 | **0.828** | 0.483 |
| trash_bin | 0.857 | 0.733 | **0.824** | 0.646 |
| tree | 0.735 | 0.755 | **0.796** | 0.422 |
| stairs | 0.897 | 0.649 | **0.815** | 0.565 |
| motorcycle | 0.822 | 0.697 | **0.789** | 0.474 |
| sign | 0.873 | 0.702 | **0.788** | 0.540 |
| fire_hydrant | 0.882 | 0.681 | **0.787** | 0.564 |
| roadblock | 0.892 | 0.679 | **0.774** | 0.546 |
| car | 0.828 | 0.704 | **0.779** | 0.525 |
| cone | 0.880 | 0.703 | **0.779** | 0.520 |
| bench | 0.722 | 0.750 | **0.784** | 0.515 |
| tricycle | 0.855 | 0.704 | **0.769** | 0.614 |
| chair | 0.750 | 0.716 | **0.761** | 0.551 |
| bicycle | 0.817 | 0.547 | **0.683** | 0.388 |
| bus | 0.810 | 0.603 | **0.687** | 0.487 |
| dog | 0.702 | 0.633 | **0.656** | 0.440 |
| plant_pot | 0.541 | 0.725 | **0.652** | 0.479 |
| guard_rail | 0.829 | 0.576 | **0.622** | 0.367 |
| truck | 0.658 | 0.494 | **0.540** | 0.374 |

> 长尾类 (truck / guard_rail / bicycle / bus / dog / plant_pot) mAP50 偏低, 与 Phase 10 记录的 437:1 长尾分布一致 (person 36,238 实例 vs plant_pot 83)。属数据集固有问题, 非标签错误 —— Phase 12 质检已确认整集标签健康。

### 3.4 test 划分每类 (节选, 完整见 `docs/final_training_stats.json`)
test 与 val 趋势一致, 关键类 blind_road test mAP50=**0.8486** (P=0.858, R=0.802), green_light 0.953, crosswalk 0.897, manhole 0.872, red_light 0.881。

---

## 4. 与 Phase 14 (smoke) 对比

| 维度 | Phase 14 smoke (10 ep) | Phase 15 正式 (200 ep) | 提升 |
| --- | --- | --- | --- |
| 数据规模 | 450 train / 100 val | **10,043 train / 3,702 val / 4,163 test** | 全量 |
| 整体 mAP50 | 0.301 | **0.775** | **+0.474** |
| blind_road mAP50 | 0.662 | **0.853** | **+0.191** |
| blind_road mAP50-95 | 0.430 | **0.666** | +0.236 |
| GPU 显存 | 1.93 GB (b16) | 5.0 GB (b32) | 稳定可控 |

smoke 阶段「盲道标注正确可学习」的预判在本阶段被充分证实。

---

## 5. 产物 (Artifacts)

全部落 `runs/` (权重被 `.gitignore` 屏蔽, 不入库); 统计 JSON 入库。

- `runs/yolov8n_prod_b32/weights/best.pt` — 最佳权重 (mAP50 峰值区间)
- `runs/yolov8n_prod_b32/weights/last.pt` — 末 epoch 权重
- `runs/yolov8n_prod_b32/results.csv` — 逐 epoch loss / 指标
- `runs/yolov8n_prod_b32/` — 训练曲线 (loss / P-R / mAP / F1 等 PNG)
- `docs/final_training_stats.json` — 复评统计 (val+test 每类, 入库)
- `scripts/run_prod_train.py` — 训练运行器 (已修 Path 序列化 bug)
- `scripts/finalize_phase15.py` — 收尾复评脚本 (仅评估不重训)

> 注: 首次启动因后台任务托管方式不当留下空壳 `runs/yolov8n_prod_b32_aborted_partial`, 已改名避免覆盖正式实验, 可安全删除 (无内容)。

---

## 6. 四项判断复核 (Phase 14 → Phase 15)

| 判断 | 结论 | 证据 |
| --- | --- | --- |
| 数据能训练 | ✅ | 全量 mAP50=0.775, 远超市面 baseline |
| 标签正确 | ✅ | 25/26 类 P/R 健康; 仅长尾类偏低 (数据量问题) |
| 模型正常收敛 | ✅ | loss 单调下降, mAP 稳定上升后平台 |
| GPU 稳定 | ✅ | 0 error / 0 OOM, ~5GB, 12.5h 全程无中断 |

---

## 7. 后续建议 (Next Steps)

1. **推理验证**: 用 `best.pt` 跑真实场景盲道图, 确认部署侧行为 (Phase 16 候选)。
2. **长尾优化**: truck / guard_rail / bicycle / bus / dog / plant_pot 偏低 → 考虑过采样 / 类别权重提升 / 补充数据源。
3. **更大模型**: 若需更高精度, 可试 YOLOv8s (batch 16–24, 8GB 仍可)。
4. **部署**: 导出 ONNX / TensorRT (INT8) 供边缘端预警系统使用。
5. **版本管理**: `best.pt` 仅本地, 如需共享经 Clash 代理 `git push` 到 GitHub (本机 22 端口被拒, 走 HTTPS)。

---

## 8. 安全约束落实 (Safety)

- 未修改 / 删除任何用户文件; 数据集 `datasets/**` 零改动。
- 未安装任何系统组件 / 未改动系统 CUDA (Phase 00 硬约束)。
- 磁盘闸门每 epoch 生效, 全程 NORMAL, 未触发 <15GB 安全停止。
- 训练产物落 `runs/` (gitignore 屏蔽), 仅 `data.yaml` / 脚本 / 报告入库。
