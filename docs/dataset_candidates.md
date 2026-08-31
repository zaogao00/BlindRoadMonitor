# 数据集候选调研报告 — Phase 08（复查更新）

> **阶段性质**：纯调查研究（Investigation Only）。本阶段**未下载、未解压、未训练、未转换**任何数据集。
> **硬件约束**：NVIDIA RTX 5070 Laptop GPU, 8 GB VRAM；D 盘剩余空间充足（实时探测 **79.2 GB, NORMAL**）。
> **后续下载纪律**：任何数据集下载 / 解压前，必须调用 `scripts/disk_manager.py` 的 `check_before_operation()` 做空间闸门校验，状态低于 `NORMAL` 时禁止扩大数据规模。
> **检索日期**：2026-09-01（复查重跑，覆盖 GuideTWSI / Tenji10K / TWSI / tactile paving / blind sidewalk / obstacle detection sidewalk 关键词；来源：官方项目页、GitHub、论文、Hugging Face、Zenodo、Kaggle、Roboflow）
> **上版基线**：2026-08-31 首版调研（原 `dataset_candidates.md`），本次在其上复查确认并补充新发现。

---

## 一、候选数据集总览对照表

| # | 数据集 | 论文/会议 | License | 图片数 | 盲道(触觉铺路) | 障碍物 | Seg | Det | YOLO 适合 |
|---|--------|-----------|---------|--------|:----:|:----:|:----:|:----:|:----:|
| 1 | **GuideTWSI** | Hwang et al., ICRA 2026 (Best Paper Finalist) | **MIT** | **39.5K** | ✅ 条状+圆点 | ❌ | ✅ | ✅(bbox+seg) | ✅✅ 最佳 |
| 2 | **WOTR** (Walk On The Road) | Xia et al., Displays 2023 | **MIT** | **13,928** | ✅(blind_road) | ✅ 15类 | ❌ | ✅(bbox) | ✅✅ 最佳 |
| 3 | **Tenji10K** | Takano et al., IEEJ TEE 2024 | 未明示( Wiley/作者授权) | 10,000 | ✅ 条状(点字ブロック) | ❌ | ✅(双边界线) | △线表示 | △ 需转换 |
| 4 | **SideGuide** | Park et al., IROS 2020 | 申请制/研究用途 | 350K(bbox)+100K(mask) | △(含 tactile 类) | ✅ 大量 | ✅ | ✅ | △ 体量过大 |
| 5 | **TP-Dataset** (GRFB-UNet) | Zhang et al., ESWA | **CC BY-NC-SA 3.0**(非商业) | 1,391 | ✅ 二分类 | ❌ | ✅ | ❌ | △ 需转 seg |
| 6 | **SToP** (Synthetic) | arXiv 2409.11164 (2024) | 未明示(论文称公开) | ~3,000+ | ✅ 圆点(ADA) | ❌ | ✅ | ✅(bbox) | ✅ 合成增强 |
| 7 | **Obstacles in Public Spaces** (Dist-YOLO) | Kaggle 社区 | **CC0 公有领域** | 3,350 | ❌ | ✅ 23类 | ❌ | ✅(YOLO原生) | ✅ 障碍物补充 |
| 8 | **BLV-Road-Nav-Accessibility** | GitHub 社区 (2026) | 需查(未明示) | 21 视频/90 类 | △(含盲道相关) | ✅ 90 类 | ❌ | ✅(bbox) | ✅ 视频/障碍物补充 |
| 9 | **TactPav** | ECNU (Springer 2025) | 需查(论文/作者) | 未公开数量 | ✅ 盲道导航 | △ | ✅(VLM 标注) | ✅(VLM 标注) | △ 多模态为主 |
| 10 | **Roboflow: crosswalk-tactile-blocks** | Roboflow 社区 | CC BY 4.0 | 未公开数量(小) | ✅ 条状/圆点 | ❌ | ✅ | ✅ | ✅ 小规模试用 |
| 11 | **Roboflow: tactile-paving-segmentation** | Roboflow (thesis) | 需查 | 未公开数量(小) | ✅ | ❌ | ✅ | ❌ | ✅ 小规模试用 |
| — | ROD-Dataset / Mendeley VI | HF / Mendeley | CC BY 4.0 | 24,326 / 8,114 | △ / ✅ | ✅ | △(部分) | ✅ | ✅ 备选补充 |

> 标注缩写：Seg = 语义/实例分割（mask）；Det = 目标检测（bounding box）。"需查" = 检索未明示，下载前需向来源方确认。

---

## 二、逐候选详细记录

### 1. GuideTWSI ⭐（推荐主用 — 盲道专精）

| 字段 | 内容 |
|------|------|
| **名称** | GuideTWSI: A Diverse Tactile Walking Surface Indicator Dataset |
| **论文** | Hwang, Yang, Nguyen, et al. *GuideTWSI: A Diverse TWSI Dataset from Synthetic and Real-World Images for Blind and Low-Vision Navigation*. **ICRA 2026**, Best Paper Finalist (Field & Service Robotics). arXiv:2603.07060；官方 PDF 见 UMass 镜像 |
| **官方来源** | 项目主页: `https://guidedogrobot-tactile.github.io/` ｜ GitHub（Sulzer Lab @ Columbia 关联，需在项目页确认最终仓库地址）｜ Kaggle / HF: `guidedogrobot` 相关条目 |
| **License** | **MIT**（代码与数据集均 MIT，可商用、可改） |
| **图片数量** | **39.5K**（三大子集）：RBar-22K ≈22K 真实图（亚洲为主，条状盲道）；SDome-15K 15K+ 合成（圆点盲道）；RDome-2K 2.4K+ 真实机器人采集（美国，圆点盲道） |
| **标注类型** | 分割掩码（polygon / RLE）+ 2D 边界框（COCO，合成集含）+ 深度图（合成集）；提供 YOLOv11-seg 格式（polygon-only）及格式转换器 |
| **是否包含盲道** | ✅ 同时覆盖**条状盲道(directional bars)** 与 **圆点盲道(truncated domes)**，地理多样性最强 |
| **是否包含障碍物** | ❌ 仅聚焦 TWSI 触觉地标本身 |
| **是否 segmentation** | ✅ 主力标注为分割掩码 |
| **是否 detection** | ✅ 合成集提供 COCO bbox；论文用 YOLOv11-seg 训练检测+分割 |
| **数据大小** | 检索未给出精确体积；依 39.5K 图粗估约 **15–30 GB**（全量）；仅取 RBar-22K 子集约 5–10 GB |
| **下载方式** | Kaggle 网页下载，或 `huggingface-cli download ...GuideTWSI`（需确认门控状态）；预训练 YOLO 权重仓库 `GuideTWSI-weights` |
| **是否适合 YOLO** | ✅✅ **最佳**。官方即用 Ultralytics(YOLOv11-seg) 训练并给出权重；提供格式转换脚本 |

**亮点**：规模最大、最多样；合成数据增强让 dome 分割 mIoU 最高 +29 点；真实机器人实测停止成功率 96.15%。MIT 授权。**风险点**：Phase 09 曾记录其 HF/Kaggle 需鉴权（401/Kaggle 登录），本环境无凭证时不可直接拉取；复查未改变这一结论，正式获取前需再次确认渠道可达性。

---

### 2. WOTR (Walk On The Road) ⭐（推荐主用 — 盲道+障碍物一体）

| 字段 | 内容 |
|------|------|
| **名称** | WOTR: A Dataset for the Visually Impaired Walk On The Road |
| **论文** | Xia, Yao, Tan, Song. *A dataset for the visually impaired walk on the road*. **Displays**, 2023. DOI: 10.1016/j.displa.2023.102486 |
| **官方来源** | GitHub: `https://github.com/kxzr/WOTR`（README 含 Baidu CODE / Google Drive 链接，复查确认仓库与 README 在线）；类别含 `tactile_paving`(→ blind_road)、`roadblock`、`warning_column`、`reflective_cone`、`pole` 等 20 类 |
| **License** | **MIT** |
| **图片数量** | **13,928** 张（train 9056 / val 2338 / test 2534），约 190K 标注框 |
| **标注类型** | **PASCAL-VOC 格式边界框**（20 类：15 障碍物 + 5 路况判断）；类映射 `data.yaml` 已给出，易转 YOLO txt |
| **是否包含盲道** | ✅ 专设 `tactile_paving`(盲道) 类 |
| **是否包含障碍物** | ✅✅ 15 类障碍物（树、路障、警示柱、反光锥、灰罐、行人、自行车、公交、卡车、汽车、摩托、三轮、消防栓、路障柱、垃圾箱等） |
| **是否 segmentation** | ❌ 仅检测框 |
| **是否 detection** | ✅ 边界框 |
| **数据大小** | 13,928 张街景图粗估约 **2–4 GB** |
| **下载方式** | GitHub 仓库 README 内 Baidu CODE（提取码 WOTR）/ Google Drive 链接 |
| **是否适合 YOLO** | ✅✅ **最佳**。VOC 框直接转 YOLO；论文配套 PC-YOLO(YOLOv7)，社区已用 YOLOv8/v11 验证 |

**亮点**：**唯一同时覆盖「盲道类 + 多类障碍物」且 MIT 授权**的数据集，最贴合本项目「盲道障碍物监测」目标。体量适中，8 GB 显存可全量训练。

---

### 3. Tenji10K

| 字段 | 内容 |
|------|------|
| **名称** | Tenji10K（Tenji = 点字/触觉；日本式触觉铺路） |
| **论文** | Takano, Nakane, Yu, Zhang. *Tactile Paving Detection and Tracking Using Tenji10K Dataset*. **IEEJ TEE**, 2024. DOI: 10.1002/tee.24123（复查确认 Wiley 在线可查） |
| **官方来源** | 论文（Wiley/IEEJ）；原数据集需向作者申请。社区二次上传见 Roboflow `vcane-4xewm/tenji-from-10k`、`pure-tenji-10k`（仅 ~100 张，CC BY 4.0） |
| **License** | 原数据集**未明示开源许可**（© IEEJ & Wiley）；社区 Roboflow 子集为 CC BY 4.0 但仅百张 |
| **图片数量** | **10,000** 张（20 个序列的第一视角视频帧），日本实地采集，640×480@30fps，智能眼镜 1.7m 高度 |
| **标注类型** | 每张图配触觉铺路**掩码，以两条边界线表示**；非标准多边形/框 |
| **是否包含盲道** | ✅ 日本式**条状盲道（点字ブロック / directional bars）** |
| **是否包含障碍物** | ❌ |
| **是否 segmentation** | ✅（双边界线掩码） |
| **是否 detection** | △ 线表示，非标准 bbox |
| **数据大小** | 10K 张 640×480 粗估约 **1–2 GB** |
| **下载方式** | 原数据联系论文作者；社区小子集见 Roboflow |
| **是否适合 YOLO** | △ 标注形态特殊（双线），需转换；全量难获取、许可不明，**不推荐直接采用** |

---

### 4. SideGuide

| 字段 | 内容 |
|------|------|
| **名称** | SideGuide: A Large-scale Sidewalk Dataset for Guiding Impaired People |
| **论文** | Park, Oh, Ham, Joo, et al. *SideGuide...*. **IROS 2020** (KAIST). DOI: 10.1109/IROS45743.2020.9340734 |
| **官方来源** | Project: `https://ytaek-oh.github.io/sideguide`（需填问卷+同意条款后获下载链接）；KAIST 实验室页面确认 (`ee.kaist.ac.kr/en/ai-in-signal/18498`) |
| **License** | **申请制 / 研究用途**（要求同意 T&C、填问卷审批，非宽松开源） |
| **图片数量** | **350K** 图含 bbox 标注 + **100K** 图含 polygon mask + 180K 立体图像对 |
| **标注类型** | 实例级 bbox + polygon mask + 立体视差 |
| **是否包含盲道** | △ GuideTWSI 曾从中提取 tactile paving 类，但原集以通用障碍物为主 |
| **是否包含障碍物** | ✅✅ 大量人行道障碍物（行人、车辆、动物、护栏、杆状物等） |
| **是否 segmentation** | ✅ |
| **是否 detection** | ✅ |
| **数据大小** | 超大（350K+ 图 + 立体对），粗估 **数十 GB** |
| **下载方式** | 官网问卷申请审批；韩国 AI Hub |
| **是否适合 YOLO** | △ 格式可用但**体量过大 + 许可限制**，对 8GB 显存/有限磁盘不友好 |

---

### 5. TP-Dataset（GRFB-UNet）

| 字段 | 内容 |
|------|------|
| **名称** | TP-Dataset（Tactile Paving Dataset，盲道分割数据集） |
| **论文** | Zhang, Liang, Zhao, Wang. *GRFB-UNet: A new multiscale attention network... for tactile paving segmentation*. **Expert Systems with Applications** |
| **官方来源** | GitHub: `https://github.com/Chon2020/GRFB-Unet`（复查确认仓库与 README 在线；代码+样例；全量数据 Baidu Netdisk 密码 9ope / Google Drive） |
| **License** | **CC BY-NC-SA 3.0（署名-非商业-相同方式共享）** — ⚠️ **非商业用途限制** |
| **图片数量** | **1,391** 张（train 824 / val 281 / test 286），多场景盲道 |
| **标注类型** | 二分类**语义分割掩码（PNG）**：盲道 vs 背景 |
| **是否包含盲道** | ✅ 盲道分割 |
| **是否包含障碍物** | ❌ |
| **是否 segmentation** | ✅ |
| **是否 detection** | ❌（仅分割） |
| **数据大小** | 小，约 **数百 MB** |
| **下载方式** | Baidu Netdisk / Google Drive（链接见 GitHub README） |
| **是否适合 YOLO** | △ 分割 PNG，需转 YOLO-seg；且 **NC 许可**限制商用，仅作非商业研究备选 |

---

### 6. SToP（Synthetic Tactile-on-Paving，合成）

| 字段 | 内容 |
|------|------|
| **名称** | SToP: Synthetic Tactile-on-Paving Dataset |
| **论文** | *Synthetic data augmentation for robotic mobility aids to support blind and low vision people*. **arXiv:2409.11164** (2024) |
| **官方来源** | 项目主页: `https://hchlhwang.github.io/SToP/`（复查确认在线） |
| **License** | **未明示**（论文称 publicly available，需查代码仓库确认） |
| **图片数量** | **~3,000+** 图像-框对（论文用 3,000 对训练 YOLOv8m） |
| **标注类型** | bbox + 分割掩码 + 深度 + 相机内参（NDDS 工具生成）；盲道按 ADA blister 型（圆点）建模 |
| **是否包含盲道** | ✅ 圆点盲道（美国式） |
| **是否包含障碍物** | ❌（另有 Synthetic Street Crossing 子集含车辆/信号灯，非盲道） |
| **是否 segmentation** | ✅ |
| **是否 detection** | ✅（已用于训练 YOLOv8 / YOLO-World） |
| **数据大小** | 小，合成图约 **1 GB 内** |
| **下载方式** | 见论文/项目主页 |
| **是否适合 YOLO** | ✅ 已验证 YOLOv8 检测；适合作为**合成增强**补充真实数据域差距 |

---

### 7. Obstacles in Public Spaces（Dist-YOLO，Kaggle 社区）

| 字段 | 内容 |
|------|------|
| **名称** | Obstacles in Public Spaces for Dist-YOLO（复查发现 Kaggle 另有同名变体 `image-obstacle-in-public-spaces`） |
| **论文/来源** | Kaggle 社区数据集（为 Dist-YOLO 模型标注） |
| **官方来源** | `https://www.kaggle.com/datasets/muftirestumahesa/obstacles-in-public-spaces-for-dist-yolo` ｜ `https://www.kaggle.com/datasets/muftirestumahesa/image-obstacle-in-public-spaces` |
| **License** | **CC0 公有领域**（可任意使用，无需署名） |
| **图片数量** | **3,350** 张 |
| **标注类型** | **YOLO Darknet txt 原生格式**（含距离信息的扩展标注） |
| **是否包含盲道** | ❌ |
| **是否包含障碍物** | ✅ 23 类（路障、坑洼、垃圾桶、椅、树、杆、斑马线、车辆、行人、闸门、楼梯等） |
| **是否 segmentation** | ❌ |
| **是否 detection** | ✅（YOLO 原生） |
| **数据大小** | 小，约 **数百 MB – 1 GB** |
| **下载方式** | Kaggle 直接下载（需 Kaggle 登录；本环境无凭证时需用户提供或走镜像） |
| **是否适合 YOLO** | ✅✅ **开箱即用**，可直接并入障碍物类别训练 |

---

### 8. BLV-Road-Nav-Accessibility（新发现 — GitHub 社区，2026）

| 字段 | 内容 |
|------|------|
| **名称** | BLV-Road-Nav-Accessibility（Blind & Low Vision 道路导航无障碍数据集） |
| **论文** | 无正式论文（GitHub 社区项目） |
| **官方来源** | GitHub: `https://github.com/Shohan29531/BLV-Road-Nav-Accessibility` |
| **License** | **需查**（仓库未在检索摘要中明示；下载前须查看 README） |
| **图片数量** | **21 个视频**（逐帧图像）+ **90 个无障碍相关目标类**的 ground truth 标注 |
| **标注类型** | 目标检测标注（视频帧）；90 类覆盖道路无障碍设施与障碍物 |
| **是否包含盲道** | △ 属"无障碍相关"范畴，具体是否含盲道类需查仓库标注清单 |
| **是否包含障碍物** | ✅ 90 类障碍物/无障碍设施 |
| **是否 segmentation** | ❌ |
| **是否 detection** | ✅ |
| **数据大小** | 视频数据，需查仓库（21 视频规模通常数百 MB – 数 GB） |
| **下载方式** | GitHub 直接 clone/download |
| **是否适合 YOLO** | ✅ 视频帧可抽帧做 bbox 检测；**适合作为障碍物类扩充**，但类目与盲道的相关性需人工核对 |

---

### 9. TactPav（新发现 — 华东师范大学 ECNU，2025）

| 字段 | 内容 |
|------|------|
| **名称** | TactPav: A Vision-Language Annotated Multi-modal Dataset for Tactile Paving Navigation |
| **论文** | ECNU（He Gaoqi 等）, Springer 章节（2025, DOI 10.1007/978-981-95-5761-5_27） |
| **官方来源** | 论文页: `https://pure.ecnu.edu.cn/en/publications/tactpav-a-vision-language-annotated-multi-modal-dataset-fortactil/`（Springer 补充材料在线） |
| **License** | **需查**（论文/作者确认） |
| **图片数量** | 未在检索摘要中公开具体数量 |
| **标注类型** | **视觉-语言（VLM）多模态标注**：图像 + 文本描述（盲道导航场景） |
| **是否包含盲道** | ✅ 盲道导航导向 |
| **是否包含障碍物** | △ 导航场景可能含障碍物描述 |
| **是否 segmentation** | ✅（VLM 标注，形式待确认） |
| **是否 detection** | ✅（VLM 标注，形式待确认） |
| **数据大小** | 需查 |
| **下载方式** | 需查（论文/作者渠道） |
| **是否适合 YOLO** | △ 以多模态 VLM 标注为主，传统 bbox/分割格式需确认；**可作为文本-图像对齐的补充**而非主训练集 |

---

### 10-11. Roboflow 社区小数据集（新发现 — 小规模试用）

| 数据集 | 来源 | License | 内容 | 是否适合 YOLO |
|--------|------|---------|------|:----:|
| **crosswalk-tactile-blocks v2** | Roboflow Universe: `https://universe.roboflow.com/crosswalk-signal-detection/crosswalk-tactile-blocksv2-2bwq2` | CC BY 4.0 | 斑马线盲道块实例分割 | ✅ 开箱即用 YOLO 格式 |
| **tactile-paving-segmentation** | Roboflow Universe: `https://universe.roboflow.com/thesis-jjmi5/tactile-paving-segmentation` | 需查 | 盲道分割 | ✅ 开箱即用 YOLO-seg |

> 两者规模小（百级–千级张），适合**快速验证 YOLO 管线**或作为盲道类别的补充，不适合独立承担主训练集。

---

### 补充候选（备选增强）

- **ROD-Dataset** (HuggingFace `Abtinzandi/Obstacle-Detection-Dataset-YOLO`，复查确认有镜像 `jiasea/Obstacle-Detection-Dataset-YOLO`)：24,326 图 / 25 类 / **YOLO Darknet txt 原生** / CC BY 4.0。含 Person, Car, Tree, Manhole, Bench, Bicycle Rack 等街具，覆盖盲道占用场景，适合扩充障碍物类。**Phase 09 已落地其 train 子集 614 图+614 标签，为本环境唯一已实际下载的数据集。**
- **Mendeley VI Navigation Dataset** (`m68g3h7p87`)：8,114 图 / 22 类 / 实例分割 + VOC / **CC BY 4.0** / 579 MB。视角贴近视障人士，含 Obstacle、Footpath、Tree、Person 等。
- **Urban Footpath Image Dataset**（DCU, doras.ie/26261）：人行道图像数据集，用于评估行人可达性（需查许可证与规模）。
- **Westley-Winks/tactile-paving-detector**（GitHub）：深度学习盲道检测小项目（需查数据规模/许可）。

---

## 三、YOLO 适用性结论

- **直接 YOLO 友好（bbox/txt 现成或可一键转）**：WOTR(VOC→YOLO)、GuideTWSI(官方 YOLO-seg + 转换器)、Obstacles in Public Spaces(原生 YOLO)、ROD(原生 YOLO)、Roboflow 两小集(原生 YOLO)。
- **需转换/增强**：TP-Dataset(分割 PNG→YOLO-seg)、SToP(已有 bbox)、Tenji10K(双线→需重标)。
- **需人工核对/多模态为主**：BLV-Road-Nav-Accessibility(90 类需核对盲道相关性)、TactPav(VLM 标注为主)。
- **不推荐主用**：SideGuide(过大+许可)、Tenji10K(许可不明+形态特殊)、TP-Dataset(NC 非商业)。

---

## 四、推荐方案

### 推荐数据集

**主训练集：WOTR（MIT）** + **GuideTWSI（MIT）**

- **WOTR** 作为系统主干：唯一同时含「盲道类(tactile_paving/blind_road)」+「15 类障碍物」且 MIT 授权的数据集，最贴合「盲道障碍物监测与预警」目标，体量适中（约 2–4 GB），8 GB 显存可全量训练。复查确认仓库/README 在线（Baidu/Drive 链接可用性需实际验证）。
- **GuideTWSI** 作为盲道专精增强：最高质量、最多样的盲道分割/检测标注（条状+圆点、真实+合成、机器人视角），MIT 授权，官方 YOLOv11-seg 权重可复用或微调；RBar-22K 子集显著强化盲道检测召回。**注意其 HF/Kaggle 获取可能仍需鉴权，需与 WOTR 的获取可行性并行验证。**

**障碍物类扩充（可选）**：ROD-Dataset (CC BY 4.0, 原生 YOLO, **本环境已可拉取/已落地 614 张样本**) 与 Obstacles in Public Spaces (CC0, 原生 YOLO) 补齐 WOTR 未覆盖的障碍物类别；BLV-Road-Nav-Accessibility 可作视频域扩充（需核对类目）。

### 理由

1. **License 安全**：WOTR 与 GuideTWSI 均为 **MIT**，可商用、可改、无申请门槛，避免 SideGuide(申请制)/TP-Dataset(非商业)/Tenji10K(不明) 的合规风险。
2. **任务匹配**：本项目监测「盲道 + 占用盲道的障碍物」，WOTR 一套数据覆盖两者；GuideTWSI 补足盲道本身的精细检测/分割。
3. **YOLO 生态就绪**：两者均提供或易转 YOLO 格式，GuideTWSI 已有 Ultralytics 训练范式与预训练权重，训练可快速起步。
4. **体量可控**：合计远小于 SideGuide，契合 RTX 5070 8GB 显存与 D 盘空间纪律。

### 预计空间（仅图片+标签，训练中间产物另计）

| 数据 | 估算体积 | 备注 |
|------|----------|------|
| WOTR 全量 | ~2–4 GB | 13,928 图 VOC |
| GuideTWSI RBar-22K（建议先取） | ~5–10 GB | 真实盲道图；全量 39.5K 约 15–30 GB |
| ROD-Dataset（已落地 614 张样本；全量 ~0.2 GB 采样） | ~0.2–0.5 GB | 可选扩充；断点续传即可 |
| Obstacles in Public Spaces | ~0.5–1 GB | 可选 |
| **第一阶段合计** | **约 8–15 GB** | 在 NORMAL(≈79 GB) 下安全 |

> ⚠️ 上述体积为粗估，**实际下载前必须以 `check_before_operation()` 闸门确认为准**；WARNING 下禁止扩大规模。

### 第一阶段建议使用多少图片

- **推荐第一阶段（管线验证 + 初版模型）**：
  - **WOTR 全量 13,928 张**（盲道 + 障碍物双任务主干）；
  - **叠加 GuideTWSI RBar-22K 中约 3,000–5,000 张盲道图**（强化盲道检测，优先条状盲道以匹配国内场景）；
  - **ROD-Dataset 已落地 614 张可先行并入**（0 成本，原生 YOLO）；
  - **合计约 17,000–19,000 张**。
- **训练配置建议（RTX 5070 8GB）**：YOLOv8n / v11n-seg，输入 640px，batch 16–24（如遇 OOM 降到 8–16），epoch 100–200。先用此规模验证 pipeline 与 mAP，再视效果决定是否引入 GuideTWSI 合成集(SDome-15K)做域增强或扩充全量。
- **不建议第一阶段**直接拉满 GuideTWSI 全量 39.5K（体积与标注异构成本高），也不建议引入 SideGuide/Tenji10K（许可/体量风险）。

---

## 五、Phase 09 衔接提示

1. 下载前必跑：`python scripts/check_disk_space.py` 与 `check_before_operation('download_dataset', required_gb=20)`。
2. 获取可行性优先级（本环境实测约束）：
   - **ROD-Dataset（HF 公开）→ 最可行**，Phase 09 断点续传脚本已就绪（`scripts/download_rod_sample.py`）；
   - **WOTR（Baidu/Drive）→ 需验证链接可达性**（本环境无 Baidu/Google 凭证，可能需要用户协助或镜像）；
   - **GuideTWSI（HF/Kaggle 鉴权）→ 需验证门控状态**，可能需要用户提供凭证。
3. 标注统一：WOTR(VOC)→YOLO txt；GuideTWSI 用官方 YOLO-seg 或格式转换器导出。
4. 类别体系设计：建议合并为「盲道 / 各类障碍物」两级，注意 WOTR 的 `tactile_paving`↔`blind_road` 与 GuideTWSI 的 tactile 类对齐。
5. 所有下载数据落入 `datasets/`（已被 `.gitignore` 屏蔽，不入库）。

---

## 六、本次复查新增/确认要点（2026-09-01）

1. **确认在线**：GuideTWSI 项目主页与论文 PDF、WOTR GitHub+README、GRFB-Unet GitHub、SToP 项目主页、Tenji10K Wiley 页面、ROD-Dataset HF（含 jiasea 镜像）。
2. **新增候选**：BLV-Road-Nav-Accessibility（GitHub, 21 视频/90 类）、TactPav（ECNU, VLM 多模态）、Roboflow crosswalk-tactile-blocks & tactile-paving-segmentation（小规模 YOLO 开箱即用）。
3. **相关研究信号（非数据集，可作方法参考）**：
   - *Street-level monitoring of urban tactile paving obstructions through visual-language models and street view imagery*（SAGE 2026, Chen & Rui）— 街景图 + VLM 监测盲道障碍物；
   - *Automated Detection and Mapping of Tactile Paving Using Street View Images*（IEEE 2025）— 街景图盲道自动检测与制图；
   - *DPSN: Dual Prior Knowledge Induced Tactile paving and Obstacle Joint Segmentation Network*（Song, Li 等）— 盲道+障碍物联合分割网络，任务与本项目一致，可作方法对标。
4. **结论不变**：主推 WOTR + GuideTWSI（MIT），ROD 为最可行补充；推荐与推荐方案维持首版结论，补充了新候选供可选增强。
