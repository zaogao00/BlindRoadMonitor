# DATASET_INFO.md — WOTR（Walk On The Road，VOC 格式全量）

> 本文件记录 Phase 09 补充下载的 WOTR 数据集（2026-09-01）。
> 获取方式：GitHub README 内 **Google Drive 公开链接**（零凭证，gdown 流程 + Range 断点续传）。
> 2026-09-01 修订：全量统计修正盲道实例数、确认 TW 为 owner 姓名、记录 `<filename>` 陷阱与多源 folder；删除冗余 WOTR.zip（解压内容已验证完整，`scripts/download_wotr.py` 可随时重下）。

## 1. 来源与许可

| 项 | 内容 |
|---|---|
| 数据集全名 | WOTR: A Dataset for the Visually Impaired Walk On The Road |
| 论文 | Xia, Yao, Tan, Song. *A dataset for the visually impaired walk on the road*. **Displays**, 2023. DOI: 10.1016/j.displa.2023.102486 |
| 官方来源 | GitHub: `https://github.com/kxzr/WOTR`（README 内 Baidu CODE:WOTR / Google Drive share link） |
| License | **MIT** |
| 格式 | **PASCAL-VOC**：Annotations(XML) / ImageSets/Main(txt) / JPEGImages |
| 规模 | **13,928 图 + 13,928 XML 标注**（train 9,056 / val 2,338 / test 2,534） |

## 2. 类别（20 类，object/name 全量统计）

| 类别 | 实例数 | 类别 | 实例数 | 类别 | 实例数 | 类别 | 实例数 |
|---|---|---|---|---|---|---|---|
| person | 35,245 | pole | 31,144 | car | 27,583 | tree | 22,515 |
| motorcycle | 12,162 | warning_column | 10,431 | crosswalk | 8,558 | bicycle | 5,995 |
| green_light | 4,965 | red_light | 4,961 | roadblock | 4,402 | reflective_cone | 4,125 |
| truck | 3,537 | sign | 3,360 | ashcan | 2,857 | **blind_road** | **2,381** |
| bus | 1,787 | tricycle | 1,580 | fire_hydrant | 1,384 | dog | 1,022 |

- **盲道（blind_road）**：全量 **1,723 张图 / 2,381 个实例**（⚠️ 曾误记为 17 张——那是按前缀抽查 2,000 个 XML 的值，blind_road 在文件后段集中分布，抽查严重低估；**以全量值为准**）。
- ⚠️ 映射（README 原文）：Annotations 中 `tactile_paving`→`blind_road`、`pedestrian`→`person`。
- ⚠️ **`TW` 不是类别**：`object/name` 仅 20 种（上表），无 TW。`TW`（926 次）出现在 `<owner><name>`，是标注者姓名（另有 78 个 `?` 及众多人名），**转换阶段无需处理**。

## 3. 落盘与校验（2026-09-01）

| 项 | 数值 |
|---|---|
| 下载 | `WOTR.zip` 4,244,840,539 B (3.95 GiB)，大小与 Drive 完全匹配，`testzip()` 通过 |
| 解压 | `datasets/raw/wotr/WOTR/` — JPEGImages **13,928** / Annotations **13,928**（配对完整） |
| ImageSets/Main | train **9,056** / val **2,338** / test **2,534**（合计 13,928 ✅） |
| 占用 | 解压 4.19 GB（zip 已删除，回收 3.95 GiB） |

## 4. 目录结构

```
datasets/raw/wotr/
├── DATASET_INFO.md        # 本文件
└── WOTR/
    ├── Annotations/       # 13,928 个 VOC XML
    ├── ImageSets/Main/    # train.txt / val.txt / test.txt
    └── JPEGImages/        # 13,928 张图
```

## 5. 转换阶段关键陷阱（⚠️ 必读）

1. **绝不能用 XML 内 `<filename>` 找图片**：全量核对 **13,926 / 13,928 个 XML 的 `<filename>`（如 `000000000064.jpg`）与磁盘图片名（如 `10000001.jpg`）不一致**（仅 2 个一致）。必须按 **「XML 文件名 stem ↔ JPEGImages 文件名 stem」配对**——该配对已验证 100% 完整。踩此坑会导致转换产出 0 条有效数据。
2. **folder 多源**：`<folder>` 分布含 img-train 6,071 / img-val 1,510 / img-test 1,742 / 新建文件夹 720 / COCO2017 926 / VOC2007 242 / train 924 / val 246 / test 245 等——WOTR 主体 + 外部源混合，不影响训练（ImageSets/Main 划分已给出）。
3. 部分 XML 残留原作者机器路径（如 `F:\DataSets\...`），不影响解析。
4. **不转换、不训练**（Phase 09 约束）；转换阶段（Phase 10 候选）需 VOC XML → YOLO txt，按映射 `tactile_paving→blind_road`、`pedestrian→person` 统一类名。

## 6. 用途

- **盲道类价值**：WOTR 是本项目唯一零凭证可获取的「含盲道类（1,723 图）+ 多类障碍物」MIT 数据集，
  与 ROD-Dataset（纯障碍物，25 类）互补：WOTR 提供盲道+街景障碍物，ROD 扩充街具类。
- 磁盘：解压后占用 4.19 GB，D 盘剩余 ~65 GB（NORMAL ≥ 30 GB）。
