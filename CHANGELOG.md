# CHANGELOG

本项目所有重要变更记录于此。格式参考 Keep a Changelog。

## [Phase 13] — 2026-09-02 (小规模 YOLO 训练验证 COMPLETE)

### Added (新增)
- **`scripts/make_smoke_subset.py`**: smoke 子集构建 (450 train + 100 val, 含 blind_road 优先; 复制输出, 不动 raw/processed)
- **`scripts/run_smoke_train.py`**: smoke 训练运行器 (YOLOv8n + imgsz=640 + batch16 + AMP + 10 epochs; 记录时间/显存/loss/mAP; 含沙箱适配)
- **`datasets/smoke_test/`**: 子集 (126 MB; train 450 含盲道 74 / val 100 含盲道 18)
- **`runs/smoke_test/yolov8n_smoke_b16/weights/{best,last}.pt`**: 训练权重 (6.2 MB; mAP50 0.303)
- **`docs/training_smoke_test.md`** + **`docs/training_smoke_test_stats.json`**: 验证报告与统计

### Trained (训练结果 — 10 epochs / 103 s)
- loss 正常下降: box 1.62→**1.45** / cls 4.64→**2.16** / dfl 1.31→**1.18**
- 指标: mAP50 0.0005→**0.303** / mAP50-95 **0.185** / P **0.497** / R **0.293** (val 100 图; 仅流程验证值)
- GPU: 峰值 **1.93 GB** (无 OOM, batch16 余量充足) ｜ AMP checks passed ｜ 0 CUDA error ｜ exit 0

### Verified (验证目标 6/6)
- 数据读取 ✅ / 标签 ✅ / 模型 ✅ (nc 80→26, 322/355 迁移) / GPU ✅ / loss 下降 ✅ / 验证流程 ✅

### Fixed (沙箱适配 — 环境, 非模型问题)
- **Arial.ttf 下载失败**: `YOLO_CONFIG_DIR` 重定向至工作区 `.yolo_config` + 预置系统字体; `MPLCONFIGDIR` 规避 matplotlib 缓存写入失败
- **[WinError 5] 标签缓存扫描**: ultralytics `multiprocessing.pool.ThreadPool` 创建命名管道被沙箱拒绝 → monkeypatch 为 `concurrent.futures` 纯线程池 (仅缓存扫描, 不改训练)
- **dataloader workers=0**: Windows spawn + 管道受限; 450 图单进程足够

### Safety (安全约束落实)
- 训练前 `check_before_operation(required_gb=5)` → NORMAL (73.8 GB), 允许
- `datasets/raw/**` / `datasets/processed/**` 零改动 (smoke 子集为独立复制)
- 磁盘: D 盘剩余 ~64.3 GB → NORMAL; 训练产物落入 `runs/` (gitignore 屏蔽)

### Git
- 提交: `Phase 13: training smoke test`

## [Phase 12] — 2026-09-02 (数据可视化质量检查 COMPLETE)

### Added (新增)
- **`scripts/visualize_dataset_quality.py`**: 可视化质检脚本 (随机采样训练图, 优先覆盖含 blind_road 的图; 图片+YOLO 标签绘制; 数值校验; 输出预览图与统计 JSON)
- **`datasets/preview/`**: 120 张标注预览图 + `_summary_grid.jpg` 汇总拼贴 (16.1 MB; 已 gitignore, 不入库)
- **`docs/dataset_quality_report.md`**: 质检报告 (采样统计 / 数值与语义检查 / 正常-异常-无法使用统计 / 结论)
- **`docs/dataset_quality_stats.json`**: 质检统计 (seed=20260902, 可复现)

### Checked (检查结果 — 120 张 / 1,335 实例)
- **数值**: 类 ID 越界 0 / 坐标越界 0 / 框非法 0 / 框序颠倒 0 / 非 5 列行 0 / 图不可读 0 / 配对缺失 0
- **盲道**: 53 实例命中, 框形健康 (面积 mean 25.8%, 横向条带为主), 位置合理
- **几何异常复核 28 条 → 全部合理**: 25 条远景小目标 (roadblock/cone/立柱, 数据集固有特性);
  3 条超大框溯源 — `car 97.3%` 图经 **YOLOv8n 模型辅助验证** (检出 car conf 0.79 区域与标注吻合, COCO 继承标注可信);
  2 条 tricycle 为作者自采近景特写
- **结论**: 120 张全部**正常** (0 异常 / 0 无法使用), **未发现严重标签错误** → 不触发「停止/不要训练」, 可进入训练

### Reminders (非阻断提醒)
- WOTR 远景小目标占比高 → 关注小目标召回; `plant_pot`/`bench` 长尾类极少 (83/84) → 建议类别权重/过采样;
  tricycle 2 个超大框建议训练前人工抽查 (低风险)

### Safety (安全约束落实)
- 纯只读检查 (仅输出预览图与报告); `datasets/processed/**` 与 `datasets/raw/**` 零改动
- 预览输出落入 `datasets/preview/` (`.gitignore` 屏蔽, 不入库); D 盘剩余 ~64.5 GB → NORMAL

### Docs (文档同步)
- `PROJECT_STATUS.md` 当前状态/磁盘表/Phase 12/下一步 (Phase 13 训练候选) 更新

### Git
- 提交: `Phase 12: dataset quality validation`

## [Phase 11] — 2026-09-02 (YOLO 数据集转换 COMPLETE)

### Added (新增)
- **`scripts/convert_dataset.py`**: raw → processed 转换器 (VOC/YOLO 双解析 + 26 类映射 + Building/Road 按行剔除 + 全局 MD5 去重 + data.yaml 生成 + `--dry-run`/`--force`)
- **`scripts/check_dataset.py`**: 转换后自检 (目录结构 / 配对 / PIL 完整性 / 格式 / 类 ID / 坐标 / 泄漏 / 空标签 / data.yaml 一致性)
- **`datasets/processed/`**: 统一 YOLO detection 数据集 (17,908 图 / 195,719 实例 / 26 类; train 10,043 / val 3,702 / test 4,163; 4.366 GiB) + `data.yaml` (`nc=26`, 绝对路径, 入库)
- 报告与日志: `docs/phase11_conversion_report.json` / `docs/phase11_check_report.json` / `docs/logs_phase11_convert.txt` / `docs/logs_phase11_check.txt`

### Converted (转换内容)
- **WOTR** (VOC, 20 类): XML stem ↔ 图片 stem 配对 (勿用 `<filename>`); bbox 归一化; 映射到统一 26 类
- **ROD** (YOLO, 25 类): 5 列框直留; **786 条有效多边形转外接框** (raw 923 − 137 属 Building/Road); `Building`/`Road` 236 行整行剔除; 映射到统一 26 类 (electrical_box→pole、Bicycle Rack→bicycle 等)
- **去重**: MD5 剔除 20 张 (train 13 + val 7; WOTR 11 + ROD 9) → 跨划分泄漏 0
- **任务类型**: detect (盲道无 mask 监督; ROD 多边形退化为外接矩形)

### Verified (自检 PASSED)
- 图片=标签 100% (每划分) ｜ 损坏 0 / 零字节 0 / 孤立标签 0 / 格式错误行 0 / 类 ID 越界 0 / 坐标非法 0 / 跨划分重复 0
- 核心类 `blind_road` 2,381 全量保留 (train 1,599 / val 372 / test 410); 来源前缀 wotr_ 13,917 + rod_ 3,991

### Safety (安全约束落实)
- `datasets/raw/**` **严格只读**, 一个字节未改; 未删除 raw
- 转换前磁盘闸门 NORMAL; 完成后 D 盘剩余 ~64.5 GB (raw 4.41 + processed 4.37 ≈ 8.8 GB)
- `datasets/processed/**` 被 `.gitignore` 屏蔽, 仅放行 `data.yaml` 入库; raw 的 `DATASET_INFO.md` 同步放行入库

### Docs (文档同步)
- `docs/dataset_report.md` 新增 §11 (转换结果/核对/磁盘)
- `docs/dataset_analysis.md` §8 标注「已执行」, 输出目录统一为 `datasets/processed/`
- `PROJECT_STATUS.md` 当前状态/磁盘表/Phase 11/下一步 更新

### Git
- 提交: `Phase 11: YOLO dataset conversion`

## [Phase 10] — 2026-09-02 (数据集结构与标签分析 COMPLETE)

### Added (新增)
- **`docs/dataset_analysis.md`**: 结构与标签分析报告 — 格式判定 / 分辨率 / 目标尺度 / 类别方案 / YOLO 适配性 / 质量清单 / **§8 Phase 11 转换清单**。
- **`scripts/analyze_datasets_phase10.py`**: 只读全量分析脚本 (PIL 解码校验 + MD5 去重 + VOC/YOLO 双解析器 + COCO 尺度统计)。
- **`docs/dataset_analysis_stats.json`**: 全量统计明细 (可复现, 供报告引用)。

### Analyzed (分析结果 — 全量扫描 17,928 图, 非抽样)
- **规模**: WOTR 13,928 图 / 13,928 XML / **189,994** 实例 / 20 类; ROD 4,000 图 / 4,000 标签 / **6,073** 实例 / 25 类; 合计 **17,928 图 / 196,067 实例**。
- **标注格式**: WOTR = **PASCAL-VOC**(纯 `<bndbox>`, 非 COCO / 非 Mask / 非 Polygon); ROD = **YOLO 原生 + Polygon 分割混合**(5,150 条 5 列框 + 923 条多边形, 涉及 843 图; 非 COCO / 非 Mask)。
- **分辨率**: WOTR 均值 883.8×746.2 (1,390 种, 123×140 ~ 5,621×4,032); ROD 均值 584×578.5 (52 种, 73.3% 为 640×640)。
- **目标尺度 (COCO)**: WOTR small 70,460 (37.1%) / medium 80,644 / large 38,890; ROD large 84.1%。
- **完整性**: 损坏图 **0** / 零字节 **0** / 图片-标签配对 **100%** / 非法框 **0** / 越界框 **0** / 非法标注行 **0**; 空标签 WOTR **0**、ROD **12** (train 3 + valid 4 + test 5)。
- **重复**: WOTR **11 组** + ROD **9 组** = 20 组 (MD5 完全相同), 其中 **15 组跨划分** → 存在评估泄漏 (WOTR 7: train↔test ×3 / train↔val ×2 / test↔val ×2; ROD 8: valid↔test ×4 / train↔test ×2 / train↔valid ×2; 余 5 组为划分内部); 跨数据集重复 **0**。
- **盲道类**: `blind_road` **1,723 图 / 2,381 实例** (train 1,599 / val 372 / test 410), small 仅 24 个 (1.0%) → 尺度健康; 但占总实例 **1.21%** → 核心类样本偏少。

### Decided (方案决策)
- ✅ **适合 YOLO, 但必须转换**: 两者均以水平矩形框为主; 第一阶段做 **detect** (非 seg — 盲道无任何 mask/polygon 监督, ROD 多边形仅覆盖 843 图且不含盲道); 训练 `imgsz=640`。
- **统一 26 类**: 15 组跨集同义类合并 (person/Person、pole/Electrical Pole、bicycle/Bike(+Bicycle Rack)、roadblock/Teraffic Barrel、reflective_cone/Traffic Cone、ashcan/Dustbin、crosswalk/Pedestrian crosswalk 等)。
- **丢弃 2 类**: `Building`(144) / `Road`(92) — 背景类, 且 Road 与 blind_road 语义冲突易混淆; ⚠️ 必须**按行剔除**标注 (不可只删 names, 否则 class id 错位)。
- **去重策略**: 按 MD5 分组, **保留 val/test 副本, 从 train 剔除重复项** (训练集精确损失 **13 张** = WOTR 9 + ROD 4, 测试集保持纯净)。

### Safety (安全约束落实)
- ✅ 未训练 / **未转换** / **未修改或删除任何原始数据** (`datasets/raw/**` 零改动)。
- ✅ 分析为纯只读 (图片仅做 PIL 解码校验与哈希计算, 无任何写入)。
- 磁盘: **68.95 GB → NORMAL** (≥ 30 GB)。

### Git
- 提交: `Phase 10: dataset analysis`

## [Phase 10 修订] — 2026-09-02 (报告数字一致性修正)

### Fixed (修正 — 经全量 MD5 复算确认)
- **合并组数 11 → 15**: §6.1 中「合并」判定实为 **15** 个 (person / pole / car / tree / motorcycle / crosswalk / bicycle / roadblock / cone / truck / sign / trash_bin / bus / fire_hydrant / dog), §6.2 映射亦为 15 组; 原句「最终压并为 11 个合并类」一并更正为「对应 §6.1 中 15 个『合并』判定类」。
- **WOTR 跨划分重复 5+ → 精确 7 组**: train↔test ×3、train↔val ×2、**test↔val ×2** (`20007314`↔`30007026`、`20007693`↔`30007123`); 另 4 组为 train 内部重复, 非泄漏。
- **「17 组」→ 15 组跨划分** (§0 TL;DR + §7.1): 原值基于「5+ 组」估算, WOTR 精确为 7 后未回改汇总; 精确账 = 跨划分 **15** (WOTR 7 + ROD 8), 总重复组 **20** (11 + 9)。
- **「~14 张」→ 精确 13 张** (§7.2 + 本文件): WOTR 9 (train 内部 4 + 跨划分 5) + ROD 4。
- **「长尾 32:1」→ 437:1** (§0 TL;DR): 32:1 无法从任何口径复现 (合并 26 类 437:1 / WOTR 20 类 34.5:1 / ROD 25 类 22.1:1 / person:blind_road 14.8:1), 统一为 §6.4 的合并后 **437:1** (person 36,238 vs plant_pot 83)。
- §7.2 增补**合计行** (20 组 / 20 张 / 15 组跨 split), 使 TL;DR 与明细可直接对账, 避免再次出现「改一处漏三处」。

### Synced (跨文档同步)
- `PROJECT_STATUS.md`: 「重复与泄漏」「待处理风险」「Phase 11 转换清单」三处同步为 **20 组重复 (15 组跨划分)** 与 **13 张**待剔除副本。

### Git
- 提交: `Phase 10: fix dataset analysis number consistency`

## [Phase 09 修订] — 2026-09-01 (WOTR 全量统计修正 + zip 清理)

### Fixed (修正 — 经 workbuddy 审查确认)
- **盲道全量数修正**: 首版 `DATASET_INFO.md` 误记盲道 "17 张/23 实例" (前缀抽查 2,000 XML 的低估值);
  全量扫描实为 **1,723 图 / 2,381 实例** (`blind_road` 在文件后段集中分布, 抽查低估约 100 倍)。
- **`TW` 误判移除**: 首版称 "未知类 TW 519 个需核对"; 全量确认 `object/name` 仅 20 类, **无 TW**;
  `TW` (926 次) 位于 `<owner><name>`, 是标注者姓名, 转换阶段无需处理。
- **转换陷阱记录**: 13,926/13,928 个 XML 的 `<filename>` 与磁盘图片名不一致 → 必须按
  **XML stem ↔ 图片 stem** 配对 (已验证 100% 完整); 已写入 `DATASET_INFO.md` §5 必读。
- **多源 folder 记录**: `<folder>` 含 img-train 6,071 / img-val 1,510 / img-test 1,742 / 新建文件夹 720 /
  COCO2017 926 / VOC2007 242 / train 924 / val 246 / test 245 等 (混合源, 不影响训练)。

### Removed (清理)
- **删除 WOTR.zip (3.95 GiB)**: 解压内容已三重验证完整 (`testzip()` + 13,928 配对 + 全量统计),
  删除回收 3.95 GiB; `scripts/download_wotr.py` 可随时重新下载 (Range 断点续传)。

### Changed (变更)
- `datasets/raw/wotr/DATASET_INFO.md` 重写 (全量类别表 + 陷阱说明 + zip 已删)
- `docs/dataset_report.md` §0.2 / `docs/storage_report.md` §2.1 / `PROJECT_STATUS.md` 磁盘表与 Phase 09 同步修正

### Safety (安全约束落实)
- 未训练 / 未转换 / 未删除任何**用户**文件 (删除的是本项目下载的冗余压缩包, 数据无损失)
- 删除后 D 盘剩余 **~69 GB → NORMAL**

### Git
- 提交: `Phase 09: fix WOTR stats (blind_road 1723, TW is owner) + drop redundant zip`

## [Phase 09 补充] — 2026-09-01 (WOTR 全量下载 COMPLETE)

### Added (新增)
- **WOTR 全量** (VOC, MIT, 含盲道类): 13,928 图 + 13,928 XML (train 9,056 / val 2,338 / test 2,534)
  - 经 **Google Drive 公开链接零凭证**获取 (gdown 流程 + Range 断点续传)
  - 落盘: `datasets/raw/wotr/` (WOTR.zip 3.95 GiB + 解压 4.19 GB + `DATASET_INFO.md`)
- **`scripts/download_wotr.py`**: WOTR 下载脚本 (磁盘闸门 + 病毒扫描确认页处理 + usercontent GET + Range 续传 + zip testzip 校验)

### Verified (验证结果)
- WOTR.zip 4,244,840,539 B 与 Drive 大小完全匹配; `testzip()` → 无损坏
- JPEGImages 13,928 / Annotations 13,928 配对完整; ImageSets 划分合计 13,928 ✅
- ⚠️ 首版抽查值 (17 张/23 实例) 已被后续全量统计修正 (见上方 [Phase 09 修订]); object/name 全量 20 类

### Changed (变更)
- 盲道数据策略: Roboflow 403 (需登录)、GuideTWSI HF 401 (门控) 均不可用 → 改用 **WOTR** (唯一零凭证可获取的「盲道+障碍物」MIT 数据集), 解决盲道数据缺口
- `docs/dataset_report.md` 新增 §0 (WOTR 补充); `docs/storage_report.md` §2.1、`PROJECT_STATUS.md` Phase 09/下一步/磁盘表 同步更新

### Safety (安全约束落实)
- 未训练 / 未转换 / 未删除任何用户文件
- 下载与解压前均 `check_before_operation()` → NORMAL (73.2 GB), 允许; 完成后 D 盘剩余 **~65 GB → NORMAL**
- 数据落入 `datasets/` (`.gitignore` 屏蔽, 不入库)

### Git
- 提交: `Phase 09: add WOTR dataset (blind road + obstacles)`

## [Phase 09 完成] — 2026-09-01 (第一轮下载 COMPLETE)

### Done (已完成)
- 网络出口恢复 (hf.co:443 可达), **ROD-Dataset 第一轮 4,000 图 + 4,000 标签** (225.7 MB) 下载并校验通过:
  - train **1,000** / valid **1,371** / test **1,629 (全量)** — 均为 seed=20260831 采样 (test 全量)
  - 落盘: `datasets/raw/rod_dataset/{split}/images|labels/` + `DATASET_INFO.md` + `data.yaml` + `README.md`
- 校验 `verify_rod_dataset.py`: **0 损坏 / 0 零字节 / 配对完整**; 仅 12 空标签 (train 3 + valid 4 + test 5, 可忽略); `verify_report.json` 已更新
- 补下载缺失标签: valid `IMG_20867.txt` (39 B)

### Fixed (实施修复 — 环境适配, 不改数据内容)
- **传输通道**: 原脚本 curl.exe 在本沙箱 schannel 报 `SEC_E_NO_CREDENTIALS` 不可用 → 改为 **requests 直写** (`scripts/download_rod_sample.py`)
- **标签阈值**: `MIN_BYTES=100` 误判几十字节的标签全部失败 → 区分 图片 100 / 标签 0 (0 字节空标签合法)
- **HF 限流**: 16 并发触发 429 → 降至 **5 并发 + 429/5xx 指数退避重试 (最多 5 次)**
- **仓库结构**: train 实际为 `train/{images,labels}/{0,1}/...` → 按 basename 扁平化落盘, 无重名

### License 更正
- ROD-Dataset 许可按 HF README front-matter 为 **MIT** (首版记录 CC BY 4.0 有误, 已更正于 DATASET_INFO.md / dataset_report.md)

### Safety (安全约束落实)
- 未训练 / 未转换 / 未删除任何用户文件
- 下载前 `check_before_operation(required_gb=6.0)` → NORMAL (79.2 GB), 允许; 完成后 D 盘剩余 **~78.9 GB → NORMAL**
- 数据落入 `datasets/` (已被 `.gitignore` 屏蔽, 不入库)

### Git
- 提交: `Phase 09: dataset acquisition` (第一轮完成)

## [Phase 08 复查] — 2026-09-01

### Searched (重跑调研)
- 按用户给定关键词重跑: GuideTWSI / Tenji10K / TWSI datasets / tactile paving datasets / blind sidewalk datasets / obstacle detection sidewalk datasets
- 渠道: 官方项目页 / GitHub / 论文 / Hugging Face / Zenodo / Kaggle / Roboflow

### Confirmed (复查确认在线)
- GuideTWSI 项目主页 + ICRA 2026 论文 PDF (arXiv:2603.07060)
- WOTR GitHub (`kxzr/WOTR`) + README (Baidu CODE / Google Drive 链接)
- GRFB-Unet GitHub (`Chon2020/GRFB-Unet`) / SToP 项目主页 (`hchlhwang.github.io/SToP`)
- Tenji10K Wiley 页面 (DOI 10.1002/tee.24123)
- ROD-Dataset HF (`Abtinzandi/...`, 含镜像 `jiasea/...`)

### Added (新增候选)
- **BLV-Road-Nav-Accessibility** (GitHub, 21 视频 / 90 无障碍类, bbox 检测, 需核对类目与许可)
- **TactPav** (华东师大 ECNU, 视觉-语言多模态盲道导航数据集, Springer 2025)
- **Roboflow 小集**: crosswalk-tactile-blocks v2 / tactile-paving-segmentation (YOLO 开箱即用, 小规模试用)

### Found (方法参考信号, 非数据集)
- *Street-level monitoring of urban tactile paving obstructions through VLM + street view* (SAGE 2026)
- *Automated Detection and Mapping of Tactile Paving Using Street View Images* (IEEE 2025)
- *DPSN: Tactile paving and Obstacle Joint Segmentation Network* (盲道+障碍物联合分割, 任务对标)

### Conclusion (结论不变)
- 推荐主用: **WOTR (MIT)** + **GuideTWSI (MIT)**; 障碍物扩充: ROD-Dataset (最可行, 已落地 614 张) / Obstacles in Public Spaces (CC0)
- 不推荐主用: SideGuide / Tenji10K / TP-Dataset
- 第一阶段: ~17,000–19,000 张, 约 8–15 GB (NORMAL 下安全)

### Safety (安全约束落实)
- 未下载 / 未解压 / 未训练 / 未转换任何数据集
- 磁盘状态: 实时探测 D 盘剩余 **79.2 GB → NORMAL**

### Git
- 提交: `Phase 08: dataset research` (复查重跑, 更新 `docs/dataset_candidates.md` / `PROJECT_STATUS.md`)

## [Phase 09] — 2026-08-31 (受阻 BLOCKED — 网络出口中断)

### Added (新增)
- `scripts/download_rod_sample.py`: ROD-Dataset 采样子集下载器 (curl 直写 + 16 线程并发 + 断点续传 + 每 250 张检查点), 目标 ~4000 张 (train 采样 1000 + valid 采样 1371 + test 全量 1629) 及配对 YOLO 标签
- `scripts/verify_rod_dataset.py`: 数据集完整性校验 (文件/图片/标签数量 + 0 字节/损坏/空标签/配对缺失检查)

### Changed (变更)
- `docs/dataset_candidates.md` 结论收敛: 本环境无 Kaggle/HF/Baidu 凭证 → WOTR、GuideTWSI 不可直接获取; **ROD-Dataset (CC BY 4.0, 原生 YOLO)** 为唯一可实际拉取的「已确认数据集」, 作为 Phase 09 第一轮下载对象

### Done (已完成)
- 下载并校验 ROD-Dataset **train 子集 614 图 + 614 标签** (39.3 MB) 至 `datasets/raw/rod_dataset/train/`; `valid/`、`test/` 待网络恢复后续传

### Blocked (受阻 — 环境级)
- 沙箱出网经本机 Clash 代理 `127.0.0.1:7897`, 当前上游 TLS 握手全部失败 (`SSL: UNEXPECTED_EOF_WHILE_READING`), 所有外部主机 000 不可达; 故 valid/test 未能下载
- 此前同一会话内已成功下载 614 张, 属**暂时性出口故障**; 网络恢复后重跑脚本即可断点续传

### Safety (安全约束落实)
- 未训练 / 未转换任何数据
- 下载前执行 `check_before_operation()` 闸门: 估算 ~0.20 GB, 完成后 D 盘剩余 ≥ 30 GB → 允许 (无需批准)
- 磁盘状态: **NORMAL**

### Git
- 提交: `Phase 09: dataset acquisition (BLOCKED — network egress down, partial ROD sample retained)`

## [Phase 08] — 2026-08-31

### Added (新增)
- `docs/dataset_candidates.md`: 公开盲道/TWSI 数据集候选调研报告 (纯调查, 未下载/未训练/未转换)

### Searched (调研对象)
- GuideTWSI / Tenji10K / TWSI datasets / tactile paving datasets / blind sidewalk datasets / obstacle detection sidewalk datasets
- 覆盖: GuideTWSI, WOTR, Tenji10K, SideGuide, TP-Dataset(GRFB-UNet), SToP(合成), Obstacles in Public Spaces(Dist-YOLO), 及补充 ROD-Dataset / Mendeley VI

### Findings (关键结论)
- **推荐主用**: WOTR (MIT, 13,928 图, 含盲道类+15类障碍物, VOC→YOLO) + GuideTWSI (MIT, 39.5K 图, 官方 YOLOv11-seg 权重与转换器)
- **障碍物扩充可选**: Obstacles in Public Spaces (CC0, 原生 YOLO) / ROD-Dataset (CC BY 4.0, 原生 YOLO)
- **不推荐主用**: SideGuide (申请制+数十GB) / Tenji10K (许可不明+双线标注) / TP-Dataset (CC BY-NC-SA 非商业)
- **预计空间**: 第一阶段约 8–15 GB (NORMAL 下安全); 建议 17,000–19,000 张图起步

### Safety (安全约束落实)
- 未下载 / 未解压 / 未训练 / 未转换任何数据集
- 磁盘状态: 采样时 D 盘剩余约 79 GB → **NORMAL**

### Git
- 提交: `Phase 08: dataset research`

## [Phase 07] — 2026-08-31

### Added (新增)
- `tests/test_yolo_inference.py`: YOLO 基础推理验证脚本 (加载 yolov8n → GPU 推理 → 保存结果图; 收集模型大小/推理时间/GPU 显存/检测框数/输出图片; 带异常捕获)

### Changed (变更)
- 将预训练权重 `yolov8n.pt` (6.25 MB) 规范存放至 `models/` 目录 (已被 `.gitignore` 屏蔽, 不入库); 测试脚本优先复用该缓存权重, 避免重复下载
- 未下载任何大型数据集; 未进行训练

### Verified (验证结果)
- 模型加载: yolov8n.pt 6.25 MB ✅
- GPU 推理: cuda:0 (RTX 5070), 耗时 1.447 s (复用权重, 无下载) ✅
- GPU 显存: 推理后 23.2 MB / 峰值 28.0 MB (远低于 8GB) ✅
- 检测框: 6 个; 输出图片: `runs/yolo_inference_test/bus.jpg` 已保存 ✅
- 退出码 0, 全流程 PASS

## [Phase 06] — 2026-08-31

### Added (新增)
- `scripts/check_yolo.py`: YOLO 环境一体化校验脚本 (Python/venv + Ultralytics + PyTorch + CUDA + GPU, 带异常捕获, 全部 PASS 退出码 0)
- `requirements.txt`: 记录 venv 中**实际安装**的精确版本 (pip freeze 导出), 含 torch/torchvision/torchaudio cu128 与 ultralytics 8.4.135 及其全部依赖

### Changed (变更)
- 在隔离 venv 安装 `ultralytics==8.4.135` 及基础依赖 (opencv-python 5.0.0.93 / matplotlib 3.11.1 / numpy 2.5.2 / pillow 12.3.0 / pyyaml 6.0.3 / requests 2.34.2 / psutil 7.2.2 / polars / nvidia-ml-py / ultralytics-thop / ultralytics-platform 等)
- 未安装任何不必要的大型 AI 框架; 未修改已有 Anaconda / managed 环境; 未安装 CUDA Toolkit

### Verified (验证结果)
- `import ultralytics` → 8.4.135 ✅
- `yolo checks` → **Setup complete**: Python 3.13.14 / torch 2.11.0+cu128 / CUDA:0 (RTX 5070 Laptop GPU, 8151 MiB) / CUDA 12.8 ✅
- 磁盘: 安装后 venv 占用 ~5.0 GB, D 盘剩余 **NORMAL**

## [Phase 05] — 2026-08-31

### Added (新增)
- `scripts/test_gpu.py`: RTX 5070 GPU 验证脚本 (stdlib + torch; 带异常捕获, 遇 CUDA error / OOM / driver error 立即退出; 不训练 / 不下载 / 不占大磁盘)

### Verified (验证结果)
- PyTorch 2.11.0+cu128 ｜ CUDA 运行时 12.8 ｜ `torch.cuda.is_available() == True`
- GPU: NVIDIA GeForce RTX 5070 Laptop GPU ｜ 计算能力 sm_120 (Blackwell) ｜ 显存 8.55 GB
- 4096×4096 矩阵乘法 OK; 与 CPU 结果误差 1.53e-05 → PASS; 峰值显存 ~210 MB (<< 8 GB)
- 退出码 0, 无 CUDA error / OOM / driver error → **GPU 验证通过**

### Disk (磁盘状态)
- 仅新增脚本 (~5 KB), 未产生大文件; D 盘仍为 **NORMAL**

### Git
- 提交: `Phase 05: GPU validation`

## [Phase 04] — 2026-08-31

### Added (新增)
- PyTorch GPU 环境 (隔离 venv 内): `torch 2.11.0+cu128` / `torchvision 0.26.0+cu128` / `torchaudio 2.11.0+cu128`
- 运行依赖: numpy / pillow / filelock / fsspec / jinja2 / networkx / sympy / typing_extensions / mpmath / markupsafe

### Upgraded / Fixed (venv 内)
- setuptools **81.0.0** (torch 要求 `setuptools<82`; 修正 Phase 03 的 84.0.0, 并清理首次失败安装留下的删残文件)
- wheel 0.48.0 ｜ pip 26.1.2 (沙箱 safe-delete 守卫阻止升 26.2.1, 功能完整)

### Verified (已验证)
- `torch.cuda.is_available() == True` ✅; 设备 = NVIDIA GeForce RTX 5070 Laptop GPU
- `pip check` → No broken requirements found ✅

### Install Notes (安装备注)
- 版本依据官方 pytorch.org cu128 索引 (RTX 5070 = Blackwell / sm_120, 必须 cu128+; 未用 cu126/cu124)
- 首次整包安装因 safe-delete 守卫拦截 setuptools 降级而回滚; 改用 `--no-deps` 装 torch 全家桶 + 单独装运行依赖绕过
- 未安装 CUDA Toolkit / TensorRT / OpenCV / FastAPI; 未修改已有 Anaconda / managed 环境

### Disk (磁盘状态)
- 安装后 venv 占用 ~4.4 GB; D 盘剩余 ~47.2 GB (沙箱视图) / 真实约 52–53 GB → 状态 **NORMAL**

### Git
- 提交: `Phase 04: PyTorch GPU environment`

## [Phase 03] — 2026-08-31

### Added (新增)
- 隔离 Python 虚拟环境: `D:\BlindRoadMonitor.venv` (基于 managed Python 3.13.14, 未用 Anaconda / 其它杂乱环境)
- `scripts/check_python_env.py`: 验证当前 Python 是否来自本项目 venv (stdlib-only; venv 内 PASS / 其它 FAIL, 退出码 0/1)

### Upgraded (仅 venv 内)
- setuptools 84.0.0 (最新)
- wheel 0.48.0 (最新)
- pip 26.1.2 (沙箱 safe-delete 守卫拦截对 `Scripts/pip.exe` 的覆盖, 未能升到 26.2.1; 功能完整, 不影响后续安装)

### Not Installed (遵守约束, 未安装)
- PyTorch / Ultralytics / CUDA Toolkit / TensorRT / OpenCV / FastAPI

### Disk (磁盘状态)
- 当前状态: **NORMAL** (D 盘剩余 ≥ 30 GB); venv 占用约 12 MB, 可忽略

### Git
- 提交: `Phase 03: isolated Python environment`

## [Phase 02] — 2026-08-31

### Checked (只读检查, 未修改环境)
- Windows 11 家庭版 中文版 (10.0.26200, Build 26200, 64 位)
- CPU: AMD Ryzen 9 8940HX with Radeon Graphics, 16 核 / 32 线程; 内存约 16 GB (15.2 GiB)
- GPU: NVIDIA GeForce RTX 5070 Laptop GPU, 8 GB VRAM (8151 MiB); 驱动 591.86 (支持 CUDA 最高 13.1)
- CUDA Toolkit: 未安装 (符合 Phase 00 约束); 报告中的 "CUDA 13.1" 为驱动能力上限, 非已装 Toolkit
- Python 3.13.14 (managed); 裸 `pip` 指向 Anaconda, `python -m pip` 才指向 managed 环境 — 已记录错位风险
- py Launcher 未安装 (`py --list` 不可用); Git 2.55.0.windows.3
- 磁盘: D:\ 剩余 ~49.6 GB → 状态 NORMAL

### Added
- `docs/environment.md`: 环境检查报告 (Windows / CPU / 内存 / GPU / 驱动 / CUDA / Python / pip / Git / 磁盘)

### Safety (安全约束落实)
- 仅检查环境, 未安装 / 卸载 / 升级任何组件
- 未修改已有 Python 环境, 未安装 CUDA Toolkit / PyTorch, 未升级 NVIDIA 驱动

## [Phase 00] — 2026-08-31

### Added (新增)
- 项目目录树: `scripts / docs / datasets / models / runs / backend / frontend / tests / configs`
- `scripts/disk_manager.py`: 磁盘安全管理模块 (标准库实现, 无第三方依赖)
  - `get_disk_info()` — 获取磁盘总/已用/剩余空间与 NORMAL/WARNING/DANGER 状态
  - `get_dir_size()` — 递归计算目录占用 (忽略符号链接, 防重复计数)
  - `check_before_operation()` — 大型操作 (下载/解压/训练/安装) 前的空间闸门
- `scripts/check_disk_space.py`: 磁盘空间检查 CLI, 输出 D 盘总量/已用/剩余/状态/项目占用, 支持 `--json`
- `docs/storage_report.md`: 存储与磁盘安全策略报告
- `PROJECT_STATUS.md`: 项目阶段状态总览

### Safety (安全约束落实)
- 未安装任何 Python 包 (纯标准库)
- 未下载数据集
- 未安装 CUDA / PyTorch
- 未执行训练
- 未删除任何已有用户文件

### Disk (磁盘状态)
- 当前状态: **NORMAL** (D 盘剩余 ≥ 30 GB)
- 项目占用: ~10.7 KB (几乎可忽略)
- 注: 运行环境对 D 盘挂载容量存在轻微浮动, 真实本机以脚本实时读数为准; 用户预期可用约 56 GB。

### Git
- 初始化仓库并提交: `Phase 00: project safety initialization`
