# DATASET_INFO.md — ROD-Dataset (第一轮完成 / Round 1 Complete)

> 本文件记录 Phase 09 第一轮下载的 ROD-Dataset 子集（2026-09-01 完成）。
> 网络出口已恢复（requests 通道），下载从 614 张断点续传至 4,000 张，校验通过。

## 数据集基本信息

| 字段 | 值 |
| --- | --- |
| 名称 | ROD-Dataset: Real-Time Obstacle Detection for Smartphone-Based Assistive Vision |
| Hugging Face 仓库 | `Abtinz/Obstacle-Detection-Dataset-YOLO`（镜像 `jiasea/...`） |
| 论文/作者 | Zandi et al., Amirkabir University of Technology (2026) |
| License | **MIT** (HF README front-matter `license: mit`；⚠️ 与首版记录 CC BY 4.0 不同, 以本文件为准) |
| 标注格式 | **原生 YOLO** (每图配对同名 `.txt`, 每行 `class_id x_center y_center width height`；本仓库含少量 >5 字段分割多边形) |
| 总规模 | 24,326 图 + 24,326 标签; train 19,186 / valid 3,511 / test 1,629 |
| 类别数 | **25 类**城市障碍物 (Bike/Building/Car/Person/Stairs/Traffic sign/Electrical Pole/Road/Motorcycle/Dustbin/Dog/Manhole/Tree/Guard rail/Pedestrian crosswalk/Truck/Bus/Bench/Traffic Cone/Fire hydrant/Teraffic Barrel/Plant Pot/Electrical Box/Chair/Bicycle Rack) |
| 是否含盲道 | 否 (通用城市障碍物, 无 tactile paving 标注; 盲道专项需后续融合 WOTR/GuideTWSI) |
| 是否含障碍物 | **是** (25 类公共空间障碍物) |
| Detection | **是** (原生 YOLO 检测框) |
| Segmentation | 部分 (少量分割多边形标注) |

## 本机已落地 (Phase 09 第一轮完成)

| Split | 图片 | 标签 | 状态 |
| --- | --- | --- | --- |
| train | **1,000** | **1,000** | ✅ 随机采样 (seed=20260831) |
| valid | **1,371** | **1,371** | ✅ 随机采样 (seed=20260831)；IMG_20867 标签补下载 |
| test | **1,629** | **1,629** | ✅ 全量 |
| **合计** | **4,000** | **4,000** | **225.7 MB** |

- 落盘路径: `D:\BlindRoadMonitor\datasets\raw\rod_dataset\{split}/images|labels/`
- 校验报告: `datasets/raw/rod_dataset/verify_report.json`（0 损坏 / 0 零字节 / 仅 12 空标签: train 3 + valid 4 + test 5）
- 下载清单/检查点: `datasets/raw/rod_dataset/download_manifest.json`
- 附随文件: `data.yaml`（官方类目/路径）、`README.md`（仓库说明）

## 下载方式 (保留, 供后续补充/复现)

```bash
# 在隔离 venv 中运行 (断点续传, 跳过已存在文件)
D:\BlindRoadMonitor.venv\Scripts\python.exe D:\BlindRoadMonitor\scripts\download_rod_sample.py
# 校验完整性
D:\BlindRoadMonitor.venv\Scripts\python.exe D:\BlindRoadMonitor\scripts\verify_rod_dataset.py
```

## 实现说明 (2026-09-01)

1. **传输通道**: 原脚本用 curl.exe, 本环境沙箱 schannel 报 `SEC_E_NO_CREDENTIALS` 不可用；
   已改为 **requests 直写**（huggingface_hub 1.29.0 已装, 网络经 requests 实测可达）。
2. **标签阈值修复**: 原 `MIN_BYTES=100` 会把仅几十字节的标签误判为失败；已区分
   图片阈值 100 / 标签阈值 0（0 字节空标签也是合法文件）。
3. **限流处理**: HF 对 16 线程并发返回 429；已降至 **5 线程 + 429/5xx 指数退避重试 (最多 5 次)**。
4. **目录结构**: 仓库 train 实际为 `train/images/{0,1}/...`（标签同构），脚本下载时已扁平化为
   `train/images/...`，无重名冲突。

## 后续注意事项

- **不转换、不训练**（Phase 09 约束）；进入训练阶段前需按项目类别体系做合并/映射
  （本项目需盲道类, ROD 无盲道类, 作**障碍物扩充**用）。
- 磁盘: 本轮占用 ~0.22 GB, 完成后 D 盘剩余 ~78.9 GB（NORMAL ≥ 30 GB）。
