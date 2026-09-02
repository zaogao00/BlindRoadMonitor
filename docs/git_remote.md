# Git 远程推送指南 (docs/git_remote.md)

> 本文档记录本仓库到 GitHub 的**持久推送方式**，所有细节公开可见，便于审查与撤销。
> 更新: 2026-09-02（最终方案: **URL 内嵌凭据**——实测本环境唯一可靠方式）

## 1. 仓库信息

| 项 | 值 |
|---|---|
| 本地仓库 | `D:\BlindRoadMonitor` |
| GitHub 远程 | `https://github.com/zaogao00/BlindRoadMonitor.git` |
| 远程别名 | `origin`（URL 已内嵌凭据, 见 §2） |
| 分支 | `master` |
| 首次推送 | 2026-09-02（23 提交完整历史, 现已同步至最新） |

## 2. 认证方式（持久, 已生效）

- **方式**: HTTPS + **origin URL 内嵌 Personal Access Token (PAT)**
- 当前 origin: `https://zaogao00:<TOKEN>@github.com/zaogao00/BlindRoadMonitor.git`
- 存储位置: 仓库本地 `.git/config`（**不入 git 历史、不推到 GitHub**, 仅本机可见）
- 查看: `git remote -v`（会显示 token, 仅本机）
- **普通 `git push origin master` 即可直接推送**, 无需任何额外参数（已实测通过）

> 为何不用 credential store helper / SSH:
> - SSH 22 端口在本机网络不可达;
> - `credential.helper=store` 实测被 system 级 `manager` helper 抢占且沙箱内交互崩溃,
>   无法可靠生效 → 改用 URL 内嵌（唯一验证成功的方式）。

## 3. 如何推送（每个 Phase 完成后）

```bash
cd D:\BlindRoadMonitor
git add <改动文件>
git commit -m "<Phase XX: 描述>"
git push origin master        # 已内嵌凭据, 直接可用
```

## 4. 如何更新 TOKEN（token 过期/轮换时）

```bash
# 查看当前 URL
git remote -v
# 替换为新 token (ghp_xxx)
git remote set-url origin "https://zaogao00:<新TOKEN>@github.com/zaogao00/BlindRoadMonitor.git"
# 验证
git ls-remote origin
```

## 5. 如何撤销 / 停用

- **移除凭据**: `git remote set-url origin https://github.com/zaogao00/BlindRoadMonitor.git`（此后 push 需重新认证）
- **吊销 TOKEN**: GitHub 网站撤销该 PAT（即使本地 URL 仍含旧 token 也会失效）
- 两者都不影响已推送内容与本地仓库

## 6. 安全注意

- token 明文存在于 `.git/config`（本机 D 盘）; `.git/` 本身不入库, token 不会上传 GitHub
- 请勿把 `git remote -v` 输出或 token 粘贴到聊天/issue/日志
- 建议定期轮换 PAT（GitHub 推荐 90 天内）
- 若仓库设为 public, 任何人克隆仅获得代码（无 `.git/config` 内 token）——安全
