# 2026-10-14 GitHub 开发快照

本次将 10 月 9 日之后的本地 CRM 开发内容同步到 `codex/crm-updates-20261014`，以 `origin/main` 的 `9e098ba` 为基线。该快照用于保存与审阅，未作为新的正式发布或部署验收。

## 同步范围

- 微信多账号绑定、客户助手、统一晨报及工作台页面。
- AI 获客价值分流、作息接待、主动销售、Zoho 邮件导入和产品事实审核。
- 官网询盘/聊天 CRM 接收接口、去重及来源校验。
- Alibaba/MIC 采集状态、消息历史、桥接重试及恢复工具。
- 对应 PHP/React/Python 源码、元数据、测试、规格、文档和重新生成的前端部署产物。

同步范围为 `fsh/` Git 仓库。外层部署工作目录、备份、客户数据、环境凭据、运行日志及本地依赖不在此次上传范围内。官网 WordPress 侧部署文件仍保存在外层工作目录，本文所述官网代码为 CRM 侧接口。

## 本机验证

2026-10-14 北京时间完成：

| 检查 | 结果 |
| --- | --- |
| `make spec-check` | 通过 |
| `git diff --check` | 通过 |
| 前端 TypeScript 单元测试 | 23 通过 |
| 现有宿主前端测试 | 13 通过 |
| TypeScript 类型检查、工作台构建和销售页构建 | 通过 |
| Alibaba 及网关/恢复 Python 测试（Python 3.12） | 117 通过，11 跳过 |
| MIC 非 live 测试（Python 3.12） | 280 通过，5 跳过，1 失败 |
| `make verify-offline` Python 契约部分 | 47 通过，2 失败 |

尚需核对的失败：

1. `tests.test_phase1.RoutesContract.test_every_authenticated_mutation_has_acl_at_action_or_service_boundary` 未识别新增 `/Fusanhe/website/sync` 的 Agent 认证边界；该 API 使用 `assertAgent`，仍需审阅并更新契约覆盖。
2. `tests.test_phase1.ServiceContract.test_send_checks_are_consistent` 期望两参数的 `assertSendAllowed` 调用，当前实现增加 `$task` 参数；需核对新发送策略与契约。
3. `mic-client/tests/unit/test_crm_bridge_cli.py::test_daemon_retries_transient_failure_without_losing_checkpoint` 期望两次提交，实际为三次，提交使用同一 request ID；需核对重试次数与预期。

本机未安装 PHP，Docker daemon 未运行，因而未执行 PHP 契约、PHP lint 或隔离 EspoCRM 集成验收。本次未重新进行真实平台/微信/邮件发送、服务器部署或在线浏览器端到端验收。环境相关跳过不计为通过。

已检查待上传文件中的常见密钥格式和凭据字面量，未发现需排除的实际密钥；该检查不构成完整安全审计。既有 `.gitignore` 保留私有目录、环境文件、缓存及运行状态排除规则。
