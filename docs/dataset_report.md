# 数据集获取报告 (docs/dataset_report.md) — Phase 09

> 生成日期: 2026-08-31
> 阶段状态: **受阻 (BLOCKED)** — 网络出口中断, 仅完成部分样本下载

## 1. 目标与范围

- 第一轮目标: 下载 **3000～5000 张** 已确认数据集图片, 优先官方/训练/sample 子集。
- 已确认可下载候选 (Phase 08): WOTR (MIT) / GuideTWSI (MIT) / Obstacles in Public Spaces (CC0) / ROD-Dataset (CC BY 4.0)。
- 本环境实际可用性:
  - **WOTR** — 仅 Baidu CODE / Google Drive, 需提取码/鉴权 → 本环境无凭证, **不可直接获取**。
  - **GuideTWSI** — HF 401 门控 + Kaggle 需鉴权 → 本环境无凭证, **不可直接获取**。
  - **Obstacles in Public Spaces** — 仅 Kaggle (`muftirestumahesa/obstacles-in-public-spaces-for-dist-yolo`, CC0, 3350 图) / 第三方镜像, 同样需 Kaggle 凭证或外部镜像 → 本环境不可直接获取。
  - **ROD-Dataset** — HF 公开仓库 `Abtinz/Obstacle-Detection-Dataset-YOLO` (CC BY 4.0, 原生 YOLO, 24,326 图) → **本环境唯一可实际拉取**。

→ 结论: 第一轮下载对象锁定 **ROD-Dataset**。

## 2. 下载前磁盘闸门计算 (check_before_operation)

| 项 | 估算 |
| --- | --- |
| 当前 D 盘剩余 | ~79.4 GB (NORMAL) |
| 下载大小 (~4000 图 + 配对标签) | ~0.20 GB |
| 解压大小 | 0 (HF 已解压, 无压缩包) |
| 转换预计 | 0 (原生 YOLO, 本阶段不转换) |
| 临时空间 | ~0.20 GB (HF 缓存落 C:, 不占 D:) |
| 最终 D 盘占用 | ~0.20 GB |
| **完成后 D 盘剩余** | **~79.2 GB ≥ 30 GB → 允许, 无需等待批准** |

## 3. 实际结果 (部分)

| Split | 图片 | 标签 | 备注 |
| --- | --- | --- | --- |
| train | 614 | 614 | ✅ 已下载校验通过 (1 个空标签, 可忽略) |
| valid | 0 | 0 | ⛔ 未下载 (网络中断) |
| test | 0 | 0 | ⛔ 未下载 (网络中断) |
| 合计 | **614** | **614** | 39.3 MB |

- 落盘: `datasets/raw/rod_dataset/{split}/images|labels/`
- 校验: `scripts/verify_rod_dataset.py` → `verify_report.json` (PIL 已启用, 0 损坏 / 0 零字节 / 仅 1 空标签)
- 检查点: `download_manifest.json`

## 4. 受阻原因 (环境级, 非代码/数据集问题)

沙箱出网经本机 Clash 代理 `127.0.0.1:7897`。当前该代理**上游 TLS 握手全部失败**
(`[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol`), 表现为:

- 直接出网 (no proxy): 超时无路由。
- 经 7897 代理: `CONNECT` 隧道可建立 (HTTP 200), 但上游 TLS 握手立即被对端关闭 (EOF)。
- 受影响主机 (全部 000 不可达): example.com / google.com / pypi.org / github.com /
  huggingface.co / kaggle.com / roboflow.com / raw.githubusercontent.com。
- 此前同一会话内**已成功下载 614 张**, 证明链路本身可达 → 判定为**暂时性出口故障**。

## 5. 后续动作 (恢复条件)

1. 网络出口恢复 (Clash 代理上游可用) 后, 直接重跑:
   `D:\BlindRoadMonitor.venv\Scripts\python.exe scripts/download_rod_sample.py`
   脚本支持断点续传 (跳过已存在文件), 会从 614 张续传至 ~4000 张。
2. 重跑后执行 `scripts/verify_rod_dataset.py` 校验, 并补写完整 `DATASET_INFO.md`。
3. 若长期无法恢复 HF 出网, 可考虑: 用户手动修复/重启 Clash 代理节点、或提供 ROD-Dataset 的
   本地镜像/其它可达源 (如 Kaggle 凭证、Roboflow 导出、百度网盘等)。

## 6. 约束落实

- ✅ 未训练、未转换、未删除任何用户文件。
- ✅ 下载前执行磁盘闸门, 状态 NORMAL, 完成后 D 盘剩余 ≥ 30 GB。
- ✅ 数据落入 `datasets/` (已被 `.gitignore` 屏蔽, 不入库)。
