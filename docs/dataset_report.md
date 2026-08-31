# 数据集获取报告 (docs/dataset_report.md) — Phase 09

> 生成日期: 2026-09-01（首版 2026-08-31 受阻, 本版为**恢复后完成**）
> 阶段状态: **已完成 (COMPLETE)** — 网络出口恢复, 第一轮 4,000 张下载并校验通过

## 1. 目标与范围

- 第一轮目标: 下载 **3000～5000 张** 已确认数据集图片, 优先官方/训练/sample 子集。
- 已确认可下载候选 (Phase 08): WOTR (MIT) / GuideTWSI (MIT) / Obstacles in Public Spaces (CC0) / ROD-Dataset (MIT)。
- 本环境实际可用性:
  - **WOTR** — 仅 Baidu CODE / Google Drive, 需提取码/鉴权 → 本环境无凭证, **不可直接获取**。
  - **GuideTWSI** — HF 401 门控 + Kaggle 需鉴权 → 本环境无凭证, **不可直接获取**。
  - **Obstacles in Public Spaces** — 仅 Kaggle (`muftirestumahesa/obstacles-in-public-spaces-for-dist-yolo`, CC0, 3350 图) / 第三方镜像, 同样需 Kaggle 凭证或外部镜像 → 本环境不可直接获取。
  - **ROD-Dataset** — HF 公开仓库 `Abtinz/Obstacle-Detection-Dataset-YOLO` (原生 YOLO, 24,326 图, **MIT** 按 HF README) → **本环境唯一可实际拉取**。

→ 结论: 第一轮下载对象锁定 **ROD-Dataset**。

## 2. 下载前磁盘闸门计算 (check_before_operation)

| 项 | 估算 |
| --- | --- |
| 当前 D 盘剩余 | **79.2 GB (NORMAL)** |
| 下载大小 (~4000 图 + 配对标签) | ~0.20–0.25 GB |
| 解压大小 | 0 (HF 已解压, 无压缩包) |
| 转换预计 | 0 (原生 YOLO, 本阶段不转换) |
| 临时空间 | ~0 (requests 直写, HF 缓存落 C:, 不占 D:) |
| 最终 D 盘占用 | ~0.22 GB (实际 225.7 MB) |
| **完成后 D 盘剩余** | **~78.9 GB ≥ 30 GB → 允许, 无需等待批准** |

闸门实况: `check_before_operation('download_dataset_rod_sample', required_gb=6.0)` → **ok=True, NORMAL**。

## 3. 实际结果 (第一轮完成 ✅)

| Split | 图片 | 标签 | 备注 |
| --- | --- | --- | --- |
| train | **1,000** | **1,000** | ✅ 随机采样 (seed=20260831) |
| valid | **1,371** | **1,371** | ✅ 随机采样 (seed=20260831)；IMG_20867 标签补下载 |
| test | **1,629** | **1,629** | ✅ 全量 |
| 合计 | **4,000** | **4,000** | **225.7 MB** |

- 落盘: `datasets/raw/rod_dataset/{split}/images|labels/`
- 校验: `scripts/verify_rod_dataset.py` → `verify_report.json`
  (PIL 已启用, **0 损坏 / 0 零字节 / 配对完整**; 仅 12 空标签: train 3 + valid 4 + test 5, 可忽略)
- 检查点: `download_manifest.json` ｜ 附随: `data.yaml`、`README.md`
- 数据集说明: `datasets/raw/rod_dataset/DATASET_INFO.md`

## 4. 实施中修复的问题 (2026-09-01)

1. **传输通道 curl → requests**: 原脚本用 `curl.exe`, 本沙箱 schannel 报
   `SEC_E_NO_CREDENTIALS` (TLS 凭证不可用) 全部失败; 实测 Python `requests` 可正常访问 HF
   (HTTP 200) → 下载改为 requests 直写 (huggingface_hub 1.29.0 已安装, 仅用于列举文件)。
2. **标签阈值误判**: 原 `MIN_BYTES=100` 把仅几十字节的标签文件 (如 44 B) 判为失败,
   导致首批 "图 500 / 标签 0 / 失败 323"; 已区分 图片阈值 100 / 标签阈值 0。
3. **HF 限流 429**: 16 线程并发触发限流 (失败 2145); 已降至 **5 线程 + 429/5xx 指数退避重试
   (最多 5 次)**, 复跑后失败降至 4, 再补下载 1 个缺失标签后为 0。
4. **仓库子目录结构**: 仓库 train 实际为 `train/images/{0,1}/...` (标签同构),
   脚本按 basename 扁平化落盘, 无重名冲突。

## 5. 首版受阻记录 (2026-08-31, 已解除)

- 沙箱出网经本机 Clash 代理 `127.0.0.1:7897`, 当时上游 TLS 握手失败
  (`SSL: UNEXPECTED_EOF_WHILE_READING`), 所有外部主机不可达, 仅落地 614 张。
- 2026-09-01 实测网络出口已恢复 (hf.co:443 可达, requests 直连 HTTP 200), 断点续传完成。

## 6. 约束落实

- ✅ 未训练、未转换、未删除任何用户文件。
- ✅ 下载前执行磁盘闸门, 状态 NORMAL, 完成后 D 盘剩余 ~78.9 GB ≥ 30 GB。
- ✅ 数据落入 `datasets/` (已被 `.gitignore` 屏蔽, 不入库)。
- ✅ 脚本修复仅为适配本环境传输通道/阈值/限流, 未改变数据集内容与格式。
