# Git 远程推送指南 (docs/git_remote.md)

> 本文档记录本仓库到 GitHub 的**持久推送方式**（HTTPS + 凭据文件），所有细节公开可见，便于审查与撤销。

## 1. 仓库信息

| 项 | 值 |
|---|---|
| 本地仓库 | `D:\BlindRoadMonitor` |
| GitHub 远程 | `https://github.com/zaogao00/BlindRoadMonitor.git` |
| 远程别名 | `origin` |
| 分支 | `master` |
| 建立时间 | 2026-09-02（首次推送 23 提交完整历史） |

## 2. 认证方式（持久）

- **协议**: HTTPS（SSH 22 端口在本机沙箱不可达, 故不用 SSH）
- **凭据文件**: `D:\BlindRoadMonitor\.credentials\github.txt`
  - 内容仅一行: `https://zaogao00:<TOKEN>@github.com`（TOKEN 为 GitHub Personal Access Token, `ghp_` 开头）
- **已被 `.gitignore` 屏蔽**（`.credentials/`）→ 凭据**不会**随项目推到 GitHub
- 使用方式: git 通过 `credential.helper=store --file=...` 读取该文件完成认证

## 3. 如何推送（两种方式）

### 方式 A — 本机任意终端直接 push（推荐, helper 自动读凭据）
```bash
cd D:\BlindRoadMonitor
git push origin master
```
> 前提: 已配置 helper（见 §5 一次性配置）；若未配置则用方式 B。

### 方式 B — 显式指定凭据文件（无需配置, 沙箱/CI 也适用）
```bash
git -c credential.helper="store --file=D:\BlindRoadMonitor\.credentials\github.txt" push origin master
```

### 完整流程（新 Phase 完成后）
```bash
git add <改动文件>
git commit -m "<Phase XX: 描述>"
git push origin master        # 或方式 B
```

## 4. 如何更新 TOKEN

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → 生成新 token（勾选 `repo`）
2. 用文本编辑器打开 `D:\BlindRoadMonitor\.credentials\github.txt`
3. 把 `ghp_旧值` 替换为 `ghp_新值`，保存
4. 验证: `git -c credential.helper="store --file=D:\BlindRoadMonitor\.credentials\github.txt" ls-remote origin`

## 5. 一次性配置（可选, 让普通 `git push` 自动生效）

在仓库内执行（把凭据 helper 写入本地 git config, 仅本仓库生效）:
```bash
git config credential.helper "store --file=D:/BlindRoadMonitor/.credentials/github.txt"
```
> 未执行本步时, 直接 `git push` 会提示输入用户名/密码（沙箱内可能失败）, 用方式 B 即可。

## 6. 如何撤销 / 停用

- **停用推送认证**: 删除 `D:\BlindRoadMonitor\.credentials\github.txt`（或改名）→ 此后 push 需重新认证
- **彻底吊销 TOKEN**: GitHub 网站撤销该 PAT（即便本地文件仍在也失效）
- 两者皆不影响已推送内容与本地仓库

## 7. 安全注意

- 凭据文件含明文 TOKEN, 仅存本机 D 盘；已被 `.gitignore` 屏蔽, 确认用 `git status` 检查它不出现在未跟踪列表
- 不要将该文件内容粘贴到任何聊天/日志/issue
- 建议定期轮换 TOKEN（GitHub 推荐 90 天）
