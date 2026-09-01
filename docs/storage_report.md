# 存储与磁盘安全报告 (Storage & Disk Safety Report)

> 项目: 基于 YOLO 的智能盲道障碍物监测与预警系统
> 阶段: Phase 00 — 项目安全与磁盘管理初始化
> 生成时间: 2026-08-31

---

## 1. 磁盘安全策略 (Disk Safety Policy)

本项目以 **保护用户数据与磁盘空间为最高优先级**, 绝不因为训练 / 下载等行为导致 D 盘爆满。
所有"大型操作"(下载数据集、解压、训练、安装依赖) 执行前 **必须** 调用
`scripts/disk_manager.py` 的 `check_before_operation()` 做空间检查。

| D 盘剩余空间            | 状态       | 允许行为                                   | 禁止行为                                                       |
| ----------------------- | ---------- | ------------------------------------------ | -------------------------------------------------------------- |
| ≥ 30 GB                 | **NORMAL** | 允许正常工作                               | —                                                              |
| 15 GB ~ 30 GB           | **WARNING**| 常规开发、代码编写                         | 扩大数据规模 / 下载新大型数据集 / 自动删除文件                  |
| < 15 GB                 | **DANGER** | 仅允许查看与上报                           | 下载 / 解压 / 训练 / 删除任何用户数据 (立即停止, 等待用户指令) |

**红线原则**: 一旦进入 DANGER, 任何大型操作一律中止, 绝不在无指示情况下删除用户文件。

---

## 2. 当前磁盘状态 (Current Disk Status)

> ⚠️ 说明: 本数值来自当前运行环境 (沙箱) 对 D 盘的实时探测。沙箱对 D 盘的挂载容量会随进程略有浮动,
> 因此以下数值为 **采样时刻** 的真实读数, 并非磁盘恒定容量。在你本机真实环境下, 脚本会报告准确值。
> 你提供的预期可用空间为 **约 56 GB**, 与首次探测 (53.3 GB 剩余) 基本吻合, 均处于 NORMAL 区间。

| 指标            | 采样值 (本次)        | 备注                                   |
| --------------- | -------------------- | -------------------------------------- |
| 监控盘符        | D:\                  | 项目与数据集所在盘                     |
| 总空间          | ~200 GB              | 沙箱视图, 真实容量以本机为准           |
| 已使用          | ~150.4 GB (75.2%)    |                                        |
| 剩余空间        | ~49.6 GB             | 用户预期 ~56 GB, 均 ≥ 30 GB            |
| 当前状态        | **NORMAL**           | 允许正常工作                           |
| 项目目录占用    | 10.73 KB (10985 B)   | 仅含 Phase 00 初始化文件, 几乎可忽略   |

结论: **当前状态 NORMAL**, 远未达到 WARNING(15 GB) / DANGER(15 GB) 阈值, 可安全开展后续 Phase 工作。

### 2.1 Phase 09 更新 (数据集下载 — 第一轮完成 ✅, 2026-09-01)

- **ROD-Dataset (本机已落地)**: `datasets/raw/rod_dataset/` 下 **4,000 图 + 4,000 标签**, 约 **225.7 MB**（train 1,000 / valid 1,371 / test 1,629 全量）。
- **WOTR (本机已落地, 补充)**: `datasets/raw/wotr/` 下 **WOTR.zip 3.95 GiB + 解压 4.19 GB**（13,928 图 + 13,928 VOC XML, train 9,056 / val 2,338 / test 2,534）— 经 Google Drive 公开链接零凭证获取, 含盲道类 `tactile_paving→blind_road`。
- **磁盘闸门结果 (两次均通过)**: ROD 下载前剩余 79.2 GB → 完成后 ~78.9 GB；WOTR 下载/解压前剩余 73.2 GB → 完成后 ~65 GB。均 **NORMAL, 允许**, 无需等待批准。
- **网络恢复**: 2026-08-31 曾因沙箱出网中断受阻；2026-09-01 实测恢复 (hf.co:443 与 drive.google.com 均可达)。
- **校验**: ROD `verify_rod_dataset.py` → 0 损坏/0 零字节/配对完整; WOTR zip `testzip()` 通过 + 13,928 配对核对 ✅。
- **实施修复**: curl→requests 通道、标签字节阈值 (100→0)、HF 并发 16→5 + 429 退避；新增 `scripts/download_wotr.py` (gdown + Range 续传)。
- 项目目录占用现约 340 MB（含数据集元数据；ROD 225.7 MB + WOTR 8.1 GB 本体另计, 均已被 `.gitignore` 屏蔽）。

---

## 3. 项目目录结构 (Project Layout)

```
D:\BlindRoadMonitor\
├── scripts\      # 磁盘管理脚本 (disk_manager.py, check_disk_space.py)
├── docs\         # 文档 (本文件 storage_report.md)
├── datasets\     # 数据集 (Phase 后期使用, 当前为空)
├── models\       # 模型权重 (Phase 后期使用, 当前为空)
├── runs\         # 训练 / 推理输出 (当前为空)
├── backend\      # 后端服务 (当前为空)
├── frontend\     # 前端界面 (当前为空)
├── tests\        # 测试 (当前为空)
├── configs\      # 配置文件 (当前为空)
├── PROJECT_STATUS.md
└── CHANGELOG.md
```

---

## 4. 提供的工具 (Provided Tooling)

### scripts/disk_manager.py (stdlib-only, 无第三方依赖)
- `get_disk_info(drive)` — 获取磁盘总量 / 已用 / 剩余 + 状态判定。
- `get_dir_size(path)` — 递归计算目录占用空间 (不重复计入符号链接)。
- `format_size(num_bytes)` — 字节数转人类可读字符串。
- `check_before_operation(op_name, drive, required_gb)` — **大型操作前的空间闸门**:
  - DANGER → 一律拒绝;
  - 预估所需空间 > 剩余 → 拒绝;
  - WARNING 且操作为"扩大数据规模"类 (download/dataset/extract/train/install/…) → 拒绝;
  - 其余 → 放行。

### scripts/check_disk_space.py (stdlib-only)
- 直接运行输出: D 盘总空间 / 已使用 / 剩余 / 当前状态 / 状态策略 / 项目占用。
- 支持 `--json` 便于被其它脚本解析。
- 用法: `python scripts/check_disk_space.py` 或 `python scripts/check_disk_space.py --json`

---

## 5. 操作约束 (Operation Constraints — Phase 00)

本阶段 **严禁** 以下行为, 已严格落实:
- ❌ 不安装任何 Python 包 (脚本仅用标准库)。
- ❌ 不下载数据集。
- ❌ 不安装 CUDA / PyTorch。
- ❌ 不训练。
- ❌ 不删除任何已有用户文件 (仅新建项目目录与文件)。

---

## 6. 下一步 (Next Steps)

1. 进入后续 Phase (环境搭建 / 数据采集 / 模型训练) 前, 先运行
   `python scripts/check_disk_space.py` 确认状态仍为 NORMAL。
2. 任何下载 / 解压 / 训练动作, 在代码中调用 `check_before_operation()` 做闸门校验。
3. 若状态降至 WARNING, 暂停数据规模扩张, 仅做轻量开发;
   若降至 DANGER, 立即停止并等待用户指令。
