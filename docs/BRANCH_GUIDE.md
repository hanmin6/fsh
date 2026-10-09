# 福三和版本与分支索引

> 2026-10-09 当前开发同步：`codex/muse-crm-mcp` 包含已部署的 22005 迁移资料、采集修复、客户评级与消息中心更新。查看最新部署请读 [迁移与运维记录](MIGRATION_22001_TO_22005_2026-10-09.md)，下文的 9 月 30 日发布标签和 main 基线用于历史追溯。

更新日期：2026-09-30。Web 正式基线为 `main`，发布标签为 [`crm-web-v1.1.0`](https://github.com/hanmin6/fsh/tree/crm-web-v1.1.0)。日常部署、评审和后续开发均从 `main` 开始。

## 当前 Web 版本

1.1.0 沿用 1.0.0 的统一 UI，新增 APIMonth 文本通道和 TokenDance MiniMax H3 Max 视频工作流。图片生成暂不启用。详见 [1.1.0 发布交接](RELEASE_CRM_WEB_1.1.0.md) 和 [双通道验收](../specs/006-dual-ai-gateways/verification.md)。

统一五页工作台以 crm-web 0.5.0 为底座，整合 HIG 的会话审核、身份确认、人工接管、销售交接、队列、历史洞察以及权限与原生布局修复。保留一套 React 源码、构建产物和宿主桥接；没有引入 HIG 的第二套运行时。

入口为 `#Home/workspace`。旧 `#Home/service`、`#Home/insights` 分别进入新版消息中心和客户历史洞察。源代码在 `client/custom/ui/`，部署产物在 `client/custom/res/workspace/`。

设计和验收记录：[批准的文字设计](../specs/005-unified-crm-web/design.md)、[本次验证](../specs/005-unified-crm-web/verification.md)、[发布交接](RELEASE_CRM_WEB_1.0.0.md)。

## 已归档 Web 分支

先在 GitHub 保存精确顶端的归档标签，核对 SHA 后再删除下列远程分支。本地正在使用的 worktree、分支与未提交文件保留。

| 原分支 / 保存点 | 归档标签 | 精确提交 | 说明 |
| --- | --- | --- | --- |
| `codex/crm-web-v0.5.0` | `archive/crm-web-v0.5.0-20260930` | `bd4a2c8ecedb72b12df322464e24028177c212dc` | 新版底座，全部历史进入 main |
| `codex/web-workbench-hig` 远程 | `archive/web-workbench-hig-20260930` | `9075d392de176cb6a14fb787748830a5db219abb` | 完整 HIG 源码和提交历史保留；业务能力在统一 UI 整合 |
| HIG 本地未推送提交 | `archive/web-workbench-hig-local-20260930` | `8a8d91dcd792e16c40b0de888a777bb4eb5bf79e` | 已提交但未推送的 UI 调整；未提交文件继续留在原 worktree |
| `codex/fusanhe-crm-frontend` | `archive/fusanhe-crm-frontend-20260930` | `8f5c406a13abf663219c4303d4b2ecd4a1624a17` | 早期前端快照，已经是 main 的祖先 |
| 发布前 main | `archive/main-before-crm-web-v1-20260930` | `23f2d99020acf42818f7887fcb5ee90092c26508` | 发布前集成基线 |

需要恢复某个旧版本时，从标签新建 `codex/` 功能分支即可，例如：

```bash
git fetch origin --tags
git switch -c codex/restore-hig archive/web-workbench-hig-20260930
```

## 保留的其他分支

`codex/android-client-ui` 是 Android 快照，不属于 Web UI 整理范围。`codex/backend-api-v1`、`codex/unified-inbox-mvp`、`codex/release-crm-food-20260921`、`codex/boss-history-insights` 是已经并入 main 的后端或里程碑历史，继续保留。它们不代表额外的在用 Web 前端。

[2026-09-24 分支说明](BRANCH_GUIDE-2026-09-24.md)保存了各阶段做过的内容与当时限制。

## 后续版本管理

- `main`：唯一正式集成基线。
- `codex/<功能>`：短期开发分支，验收并入 main 后删除远程分支。
- `crm-web-vX.Y.Z`：Web 发布标签。兼容补丁升补丁号，新功能升次版本，破坏性变化升主版本。
- `archive/*`：冻结的历史保存点，不移动、不复用。

1.1.0 的临时开发分支 `codex/dual-ai-gateways-v1.1.0` 已通过 [PR #2](https://github.com/hanmin6/fsh/pull/2) 并入 `main`；发布标签核对后删除远程临时分支，开发提交由 main 历史和版本标签保留。

回滚采用新提交 revert 发布改动，或在部署系统选择旧标签；不强推 main，不回滚数据库，不删除历史标签。客户外发继续由服务端权限、审核状态和停发开关控制。
