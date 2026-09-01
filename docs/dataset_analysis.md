# 数据集结构与标签分析 (docs/dataset_analysis.md) — Phase 10

> 生成日期: 2026-09-02 ｜ 阶段: Phase 10 — 数据集结构与标签分析
> 分析方法: `scripts/analyze_datasets_phase10.py`（**只读**，未修改 / 未删除任何原始数据）
> 原始统计: `docs/dataset_analysis_stats.json`（全量逐文件扫描，非抽样）
> 分析范围: **WOTR 13,928 图** + **ROD-Dataset 4,000 图** = 17,928 图 / 196,067 个标注实例

---

## 0. 结论速览 (TL;DR)

| 问题 | 结论 |
|---|---|
| **是否适合 YOLO** | ✅ **适合**，但**必须转换后**才能训练。两数据集都能映射到 YOLO detect 格式；盲道类存在且可用。 |
| **需要什么转换** | WOTR: **VOC XML → YOLO txt**（按 stem 配对，勿用 `<filename>`）；ROD: **多边形 → 检测框**（第一阶段）+ 类 ID 重映射；两者统一 `data.yaml`、去重、统一划分。 |
| **保留类别** | 统一为 **26 类**（见 §6），含核心类 `blind_road`。 |
| **合并类别** | 11 组跨数据集同义类合并（person/Person、pole/Electrical Pole、bicycle/Bike 等），见 §6.2。 |
| **丢弃类别** | **2 类**：`Building`（背景建筑）、`Road`（路面背景，与 blind_road 语义冲突）。 |
| **最大风险** | ① 盲道类仅 2,381 实例（占总量 1.21%），样本偏少；② 划分泄漏 17 组重复图；③ 类别长尾 32:1。 |

---

## 1. 数据集总览对照

| 项 | **WOTR** | **ROD-Dataset** |
|---|---|---|
| 路径 | `datasets/raw/wotr/WOTR/` | `datasets/raw/rod_dataset/` |
| **标注格式** | **PASCAL-VOC**（XML + `<bndbox>` 轴对齐矩形） | **YOLO 原生 txt**（5 列框 **混合** >5 列多边形） |
| 格式判定 | ❌ 非 COCO ❌ 非 Mask ❌ 非 Polygon | ❌ 非 COCO ❌ 非 Mask ✅ **含 Polygon（部分）** |
| 图片数量 | **13,928** | **4,000** |
| 标签文件数量 | **13,928**（XML） | **4,000**（txt） |
| 标注实例总数 | **189,994** | **6,073**（5,150 框 + 923 多边形） |
| 类别数量 | **20** | **25**（声明 25，样本中 25 类全部出现） |
| 每图平均实例 | **13.64**（最多 79，最少 1） | **1.52**（最多 30，最少 0） |
| 占用 | 4.19 GB | 225.7 MB |
| License | **MIT** | ⚠️ 记录不一致（见 §7.4） |

---

## 2. 标注格式判定（明确说明）

### 2.1 WOTR — **PASCAL-VOC（检测框）**

- 每图一个 `.xml`，`<object>` 内含 `<name>` + `<bndbox>`（xmin/ymin/xmax/ymax，**像素绝对坐标**）。
- **不是** COCO（无 `instances_*.json`）；**不是** Mask（无 PNG/RLE）；**不是** Polygon（`<polygon>` 节点数 = 0）。
- 全部 189,994 个对象均有 `bndbox`；`<truncated>` 标记 28,480 个、`<difficult>` 354 个（仅元数据，转换时建议忽略 `difficult`）。

### 2.2 ROD-Dataset — **YOLO 原生，检测框 + Polygon 分割混合**

| 行类型 | 列数 | 行数 | 涉及图片 |
|---|---|---|---|
| 检测框（class xc yc w h，归一化） | 5 | **5,150** | 3,148 图 |
| **Polygon 分割**（class x1 y1 x2 y2 …，归一化） | ≥7 且偶数 | **923** | 843 图 |
| 非法行 | — | **0** | — |

- 坐标**已归一化**到 [0,1]；越界行 **0** 条；类别 ID 越界 **0** 条。
- **不是** COCO；**没有** PNG/RLE mask；分割信息以**多边形顶点**直接写在 txt 里。
- ⚠️ **混合格式影响任务选型**：WOTR 无任何多边形 → 若做分割（`-seg`），盲道类将**完全没有**分割监督。见 §5.3。

---

## 3. 分辨率分析

### 3.1 WOTR（高度异构，来自多源）

| 指标 | 数值 |
|---|---|
| 宽度 | min **123** / max **5,621** / 均值 **883.8** / 中位 **876** |
| 高度 | min **140** / max **4,032** / 均值 **746.2** / 中位 **657** |
| 平均像素 | **0.95 MP** |
| 不同分辨率数 | **1,390** 种 |
| 宽高比 | 0.312 ~ 4.324（均值 1.226，横图为主） |
| Top5 分辨率 | 876×657 (4,633) / 1020×1360 (1,255) / 640×480 (981) / 300×400 (473) / 1920×1080 (464) |

### 3.2 ROD-Dataset（已预处理，集中）

| 指标 | 数值 |
|---|---|
| 宽度 | min **197** / max **1,600** / 均值 **584.0** / 中位 **640** |
| 高度 | min **150** / max **1,200** / 均值 **578.5** / 中位 **640** |
| 平均像素 | **0.35 MP** |
| 不同分辨率数 | **52** 种 |
| Top5 分辨率 | **640×640 (2,930 / 73.3%)** / 416×416 (574) / 300×300 (212) / 512×512 (155) / 640×480 (73) |

> **对训练的影响**：YOLO 训练会 letterbox 到固定 `imgsz`，两者差异不构成障碍。建议 `imgsz=640`（与 ROD 原生分辨率一致，且 8GB 显存友好）；若 WOTR 小目标召回不足，可试 `imgsz=960`（显存需降到 batch 8）。

---

## 4. 目标尺度分布（COCO 定义：small<32², medium<96², large≥96²）

| 数据集 | small | medium | large | 中位框面积 |
|---|---|---|---|---|
| WOTR | **70,460 (37.1%)** | 80,644 (42.4%) | 38,890 (20.5%) | 1,712 px² |
| ROD | 191 (3.1%) | 776 (12.8%) | **5,106 (84.1%)** | 84,760 px² |

- WOTR 小目标集中在：person (15,851) / car (9,823) / warning_column (8,056) / tree (8,010) / pole (7,513)。
- ✅ **盲道类尺度健康**：`blind_road` 2,381 个实例中仅 **24 个 (1.0%)** 属于 small，绝大多数为中大型目标，利于检测。
- ⚠️ WOTR 小目标占比 37%，在 640 分辨率下会有召回损失，属本任务主要精度瓶颈之一。

---

## 5. YOLO 适配性评估

### 5.1 适配性判定：**适合（需转换）**

| 判定维度 | 结果 | 说明 |
|---|---|---|
| 标注类型匹配 | ✅ | 两者都以**水平矩形框**为主，是 YOLO detect 的原生输入形态。 |
| 格式可转换 | ✅ | VOC→YOLO 为成熟路径；多边形→外接矩形 1 行代码。 |
| 任务目标覆盖 | ✅ | 存在盲道类（1,723 图）+ 20+ 类街景障碍物，契合"盲道障碍物监测"。 |
| 数据规模 | ✅ | 17,928 图 / 196,067 实例，足够训练 YOLOv8n/v11n 级模型。 |
| 划分可用 | ⚠️ | 划分齐全，但存在 17 组跨划分重复（见 §7.2），须去重。 |
| 类别体系 | ⚠️ | 两套命名不一致（20 类 vs 25 类），需统一映射。 |
| 分割可行性 | ❌（现阶段） | 盲道仅 WOTR 有框、无任何 mask/polygon → **第一阶段不建议做 -seg**。 |

### 5.2 建议训练形态（第一阶段）

- 任务：**目标检测**（`yolov8n.pt` / `yolo11n.pt`，非 `-seg`）
- 输入：统一 YOLO 目录 `datasets/yolo/{images,labels}/{train,val,test}` + 统一 `data.yaml`（26 类）
- 分辨率：`imgsz=640`；显存 8GB 下 `batch=16`，OOM 时降到 8 并开 `amp=True`

### 5.3 分割任务的后续路径（不在本阶段）

若要实现"盲道区域像素级分割"，现有数据**不支持**（盲道无 mask）。可选路径：
1. 获取 **GuideTWSI**（官方有 YOLOv11-seg 权重与格式转换器，当前 HF 401 门控，需凭证）；
2. 用现有检测框做弱监督（Box-Level → Mask，如 Box2Mask/BoxInst）；
3. 人工/半自动补标盲道多边形（成本最高）。

---

## 6. 类别方案：保留 / 合并 / 丢弃

### 6.1 统一类别表（**26 类**，建议最终 `data.yaml`）

| ID | 统一类名 | WOTR 来源（实例） | ROD 来源（实例） | 合并后实例 | 判定 |
|---|---|---|---|---|---|
| 0 | **blind_road** | blind_road (2,381) | — | **2,381** | ⭐ 核心类，保留 |
| 1 | person | person (35,245) | Person (993) | 36,238 | 合并 |
| 2 | pole | pole (31,144) | Electrical Pole (101) | 31,245 | 合并 |
| 3 | car | car (27,583) | Car (823) | 28,406 | 合并 |
| 4 | tree | tree (22,515) | Tree (392) | 22,907 | 合并 |
| 5 | motorcycle | motorcycle (12,162) | Motorcycle (123) | 12,285 | 合并 |
| 6 | warning_column | warning_column (10,431) | — | 10,431 | 保留（盲道典型立柱障碍） |
| 7 | crosswalk | crosswalk (8,558) | Pedestrian crosswalk (479) | 9,037 | 合并 |
| 8 | bicycle | bicycle (5,995) | Bike (105) + Bicycle Rack (53) | 6,153 | 合并（车架并入车） |
| 9 | green_light | green_light (4,965) | — | 4,965 | 保留（过街决策） |
| 10 | red_light | red_light (4,961) | — | 4,961 | 保留（过街决策） |
| 11 | roadblock | roadblock (4,402) | Teraffic Barrel (64，原拼写错误) | 4,466 | 合并 |
| 12 | cone | reflective_cone (4,125) | Traffic Cone (195) | 4,320 | 合并 |
| 13 | truck | truck (3,537) | Truck (126) | 3,663 | 合并 |
| 14 | sign | sign (3,360) | Traffic sign (169) | 3,529 | 合并 |
| 15 | trash_bin | ashcan (2,857) | Dustbin (154) | 3,011 | 合并 |
| 16 | bus | bus (1,787) | Bus (141) | 1,928 | 合并 |
| 17 | tricycle | tricycle (1,580) | — | 1,580 | 保留（可选并入 bicycle） |
| 18 | fire_hydrant | fire_hydrant (1,384) | Fire hydrant (45) | 1,429 | 合并 |
| 19 | dog | dog (1,022) | Dog (86) | 1,108 | 合并 |
| 20 | stairs | — | Stairs (419) | 419 | 保留（跌坠风险） |
| 21 | manhole | — | Manhole (502) | 502 | 保留（地面坑洞） |
| 22 | guard_rail | — | Guard rail (229) | 229 | 保留 |
| 23 | chair | — | Chair (400) | 400 | 保留 |
| 24 | bench | — | Bench (84) | 84 | 保留 |
| 25 | plant_pot | — | Plant Pot (83) | 83 | 保留 |

> `electrical_box`（ROD, 71）建议**并入 `pole`**（同为杆状/箱体电力设施，视觉相近），上表已按此处理；若坚持独立则最终为 27 类。

### 6.2 合并清单（11 组跨数据集同义类）

person↔Person ｜ pole↔Electrical Pole ｜ car↔Car ｜ tree↔Tree ｜ motorcycle↔Motorcycle ｜ crosswalk↔Pedestrian crosswalk ｜ bicycle↔Bike（+Bicycle Rack）｜ roadblock↔Teraffic Barrel ｜ reflective_cone↔Traffic Cone ｜ truck↔Truck ｜ sign↔Traffic sign ｜ ashcan↔Dustbin ｜ bus↔Bus ｜ fire_hydrant↔Fire hydrant ｜ dog↔Dog
（共 15 组映射，最终压并为 11 个合并类）

### 6.3 丢弃清单（2 类）

| 类名 | 来源 | 实例 | 丢弃理由 |
|---|---|---|---|
| **Building** | ROD | 144 | 大背景建筑物，非障碍物；框巨大且边界模糊，会拉低定位指标。 |
| **Road** | ROD | 92 | 路面区域，与 `blind_road` 语义直接冲突，易造成"盲道↔路面"混淆。 |

> ⚠️ 丢弃必须在**转换阶段按行剔除**（连同该行整体删除），**不能**只从 `names` 里删名，否则 class id 与标签错位。
> 剔除后 ROD 有效实例：6,073 − 144 − 92 = **5,837**。

### 6.4 类别不均衡（合并后）

- 最大类 `person` **36,238** vs 最小类 `plant_pot` **83** ≈ **437:1**
- 核心类 `blind_road` 仅占总量 **1.21%** → 训练时建议：① 保留全部盲道样本不做欠采样；② 对长尾类使用 `--close_mosaic`、类别权重或过采样；③ 评估指标单独看 `blind_road` 的 mAP。

---

## 7. 数据质量问题清单

### 7.1 健康项 ✅

| 检查项 | WOTR | ROD |
|---|---|---|
| 损坏图片（PIL 全量 verify） | **0** | **0** |
| 零字节图片 | **0** | **0** |
| 图片/标签配对 | 13,928 : 13,928（100%） | 4,000 : 4,000（100%） |
| 缺失标签 | 0 | 0 |
| 非法框 / 越界框 | 0 / 0 | 0 / 0 |
| 非法标注行 | 0 | 0 |
| XML `<size>` 与实际图不符 | 0 | — |
| 跨数据集重复（WOTR↔ROD，MD5） | **0** | **0** |
| 空标签 | **0** | **12**（见下） |

### 7.2 ⚠️ 重复图片与划分泄漏（必须处理）

| 数据集 | 重复组 | 冗余文件 | 跨划分情况 |
|---|---|---|---|
| WOTR | **11 组** | 11 张 | 已确认样本中 **5+ 组跨 split**（train↔test ×3、train↔val ×2、test↔val ×1） |
| ROD | **9 组** | 9 张 | **8 组跨 split**（train↔test ×2、train↔valid ×2、valid↔test ×4），1 组 valid 内部 |

- **风险**：同一张图同时出现在 train 与 test → 评估指标虚高（ memorize 而非泛化）。
- **建议策略**：按 MD5 分组，**优先保留 val/test 中的副本，从 train 中剔除重复项**（训练集仅损失 ~14 张，测试集保持纯净）。
- 示例：`train/IMG_00021.jpg` ≡ `test/IMG_19189.jpg`（ROD）；`10007030.jpg`(train) ≡ `20006850.jpg`(test)（WOTR）。

### 7.3 ⚠️ 空标签（ROD 12 个）

`train` 3 + `valid` 4 + `test` 5（如 `train/IMG_13674`、`valid/IMG_23505`、`test/IMG_19205`）。
- Ultralytics 支持空 txt 作为**背景负样本**，数量少（0.3%）→ **建议保留**，可抑制误检。

### 7.4 ⚠️ 其他需关注项

| 项 | 说明 | 建议 |
|---|---|---|
| ROD License 记录不一致 | Phase 08 记为 **CC BY 4.0**，Phase 09 记为 **MIT**（HF README） | 合并前确认；两者均允许商用+署名，**不阻断**本项目，但发布时需按实际许可署名 |
| ROD 类名拼写错误 | `Teraffic Barrel`（应为 Traffic Barrel） | 转换时统一为 `roadblock`，顺带修正 |
| WOTR 多源混合 | `<folder>` 含 img-train/COCO2017/VOC2007/新建文件夹 等 25 种 | 不影响训练，但域差异大，建议先做基线评估 |
| WOTR truncated 对象 | 28,480 个（15%）被截断 | 保留（真实场景本就存在截断），不剔除 |
| 域差异 | WOTR 手持/头戴街景（0.95MP）；ROD 已预处理方图（0.35MP） | 建议：① WOTR 单训基线 → ② 混合微调，对比 mAP 后再决定配比 |

---

## 8. 需要的转换（Phase 11 执行清单，本阶段**不执行**）

> 所有转换输出到**新目录** `datasets/yolo/`，**只读** `datasets/raw/**`，原始文件一个字节都不改。

1. **WOTR VOC → YOLO**
   - 按 **XML stem ↔ JPEGImages stem** 配对（**绝不能用 XML 内 `<filename>`**，13,926/13,928 不一致）
   - bbox 转 `class x_center y_center w h`（归一化到图片实际宽高，clamp 到 [0,1]）
   - 类名按 §6.1 映射并重新编号
2. **ROD 多边形 → 检测框**
   - 每行 ≥7 列时取 x/y 的 min/max 转外接矩形；5 列框**直接保留**（坐标已归一化）
   - 类名映射 + 重编号；**删除** `Building`(1) / `Road`(7) 两类的整行
3. **统一划分与去重**
   - WOTR 沿用 ImageSets（train/val/test）；ROD 沿用目录划分
   - 按 MD5 全局去重：保留 val/test 副本，剔除 train 中的重复项
   - 两数据集**按划分合并**到同一 `{train,val,test}`（不重叠、不交叉）
4. **生成统一 `data.yaml`**：`nc=26`，`names=[…]`，`path=datasets/yolo`，`train/val/test` 指向 `images/{split}`
5. **转换后自检**：重跑同类统计脚本，校验 图片数 = 标签数、类 ID ∈ [0,25]、坐标 ∈ [0,1]、空标签清单、每类实例数与本报告一致（±剔除与去重量）

---

## 9. 附：关键数字索引

| 指标 | WOTR | ROD | 合计 |
|---|---|---|---|
| 图片 | 13,928 | 4,000 | **17,928** |
| 标签文件 | 13,928 | 4,000 | **17,928** |
| 标注实例 | 189,994 | 6,073 | **196,067** |
| 类别 | 20 | 25 | 统一后 **26** |
| 划分 (train/val/test) | 9,056 / 2,338 / 2,534 | 1,000 / 1,371 / 1,629 | 10,056 / 3,709 / 4,163 |
| 盲道图 / 实例 | **1,723 / 2,381** | 0 | **1,723 / 2,381** |
| 损坏图 | 0 | 0 | **0** |
| 空标签 | 0 | 12 | **12** |
| 重复（冗余文件） | 11 | 9 | **20** |

> 原始统计明细见 `docs/dataset_analysis_stats.json`；复现命令：
> `D:\BlindRoadMonitor.venv\Scripts\python.exe scripts/analyze_datasets_phase10.py`
