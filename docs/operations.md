# 福三和 CRM 运维手册（非渠道部分）

## 安全基线

- 生产与演练环境保持 `FUSANHE_OUTBOUND_PAUSED=true`，只有渠道正式验收窗口才允许单独解除。
- `.env`、Agent 明文凭证、客户导出和备份不得提交 Git 或粘贴到工单。
- 日志只记录 `X-Request-Id`、稳定错误码和对象 ID，不记录 Token、密码、消息全文或绝对文件路径。
- 知识库只扫描 `KNOWLEDGE_BASE_PATH` 的真实子路径；符号链接、非白名单类型及超过 `FUSANHE_KNOWLEDGE_MAX_BYTES` 的文件会被跳过或隔离报错。

## 健康检查

```bash
docker compose ps
docker compose config --quiet
curl -fsS http://localhost:8080/api/v1/Fusanhe/status
make verify-offline
```

检查 EspoCRM、数据库、daemon、websocket 都处于 healthy/running；`status` 中 `outboundPaused` 应为 `true`。任何异常先记录请求 ID，再查容器日志，禁止直接在生产库试写。

## Agent 凭证签发、轮换与撤销

1. `FUSANHE_AUTOMATION_TOKEN` 只用于 `/Fusanhe/agent/register` 的引导注册，使用长随机值并限制接触人。
2. 注册响应中的 `credential` 只出现一次，立即写入执行端系统密钥库；数据库仅保存 `password_hash`。
3. 心跳、领取、sending、result 请求使用该独立凭证，并且请求体 `agentKey` 必须与凭证绑定。
4. 再次注册同一 `agentKey` 会轮换凭证并增加版本，旧凭证立即失效。紧急撤销时设置该 Agent 的 `credentialRevokedAt`，并把状态改为 offline。
5. `FUSANHE_AUTOMATION_LEGACY_UNTIL` 为空即禁用旧共享口令回退；最迟在 **2026-10-31** 前完成迁移并保持为空。

## Made-in-China 桥接运维

CRM 默认 `FUSANHE_OUTBOUND_PAUSED=true`，且代码在变量缺省时也按 true 处理。保持停发开启完成回填、只读检查和集成准备；只有在已登记的指定目标现场验收窗口，才按正式变更流程单独解除。

### MIC key 与 CRM Agent 凭证

- 在 MIC Gateway 分别创建 `crm_read` key 和 `agent_send` key。将前者设置为 `MIC_CRM_READ_API_KEY`，后者设置为 `MIC_CRM_SEND_API_KEY`，只放进受保护的 MIC bridge 运行环境。
- `MIC_ACCOUNT_HANDLE` 标识单一 MIC 卖家账号；`MIC_GATEWAY_URL` 与 `MIC_CRM_URL` 默认分别指向本机 Gateway 和 CRM。`MIC_APP_DATA_DIR` 必须在源码树外，bridge 检查点位于其 `crm-bridge\checkpoints.sqlite3` 子目录。
- 在 MIC bridge 进程环境中短暂设置 `MIC_CRM_BOOTSTRAP_TOKEN` 为 CRM 的 `FUSANHE_AUTOMATION_TOKEN`，并设置 `MIC_CRM_AGENT_KEY`。运行 `python -m mic_gateway.crm_bridge.cli register`；默认旋转已有同名 Agent token。成功后将 stdout 中一次性返回的 CRM Agent token 交给受保护的 `MIC_CRM_AGENT_TOKEN` 配置，然后移除 bootstrap token。
- 后续注册/心跳/领取/结果请求使用绑定 `MIC_CRM_AGENT_KEY` 的独立 Agent token；不得把 `FUSANHE_AUTOMATION_TOKEN` 当日常 token。发生轮换后旧 Agent token 会失效，需要同步更新 Worker 环境。
- `MIC_CRM_ALLOW_REMOTE_HTTPS=true` 仅用于经批准且采用 HTTPS 的远程 CRM；默认配置只接受 loopback。

MIC bridge 从进程环境读取配置，不会自动加载 MIC 项目的 `.env`。Windows 计划任务/进程托管配置必须为 importer 和 Worker 提供同一组必要环境变量；不要把密钥放入命令行参数、日志、仓库或工单。

### 导入与状态

在 MIC Gateway 健康并已由专用 Chromium 用户会话登录后，运行：

```powershell
python -m mic_gateway.crm_bridge.cli status
python -m mic_gateway.crm_bridge.cli backfill
python -m mic_gateway.crm_bridge.cli once
python -m mic_gateway.crm_bridge.cli daemon --interval 60
```

`backfill` 初次导入，`once` 进行增量重读，`daemon` 默认每 60 秒扫一次并对暂时性故障退避，`status` 显示本地 cursor、pending request、冲突和最近人工决策。检查点只在 CRM 确认同一个 `requestId` 后推进。每条对话只有 MIC 明确报告 `history_complete=true` 才允许导入；缺失完整历史或无法可靠绑定页面会话身份时失败关闭，禁止把它当成空历史或标记已完成。

若 `status` 报告 `pending_batch_conflict`：

1. 在 CRM `AutomationAudit` 中查找并核对 status 输出的完全相同 `requestId`。
2. 仅审计明确为已接受时执行 `--verified-accepted`；确认未接受时执行 `--verified-not-accepted`。
3. 若 CRM 审计缺失、请求 ID 不匹配或结果不确定，保持 pending，交 CRM 运维排查。不要删除/改写 SQLite 检查点或猜测响应。

```powershell
python -m mic_gateway.crm_bridge.cli resolve-pending conversations:once `
    --request-id "<status 中的精确 requestId>" --verified-accepted
```

每次 resolve 会在 MIC 本地状态库留存资源、request ID、决策、时间戳；不保存 batch 正文。该本地记录不代替 CRM `AutomationAudit` 审计。

### 出向 Worker 与人工对账

Worker 单独于 CRM 容器运行，并需 `MIC_CRM_SEND_API_KEY` 与已注册的 `MIC_CRM_AGENT_TOKEN`：

```powershell
python -m mic_gateway.crm_bridge.run_worker --once
python -m mic_gateway.crm_bridge.run_worker --interval 30
```

Worker 只允许 `MadeInChina` 且 `real` 模式的已批准 CRM 任务；CRM 的 `claim`、`sending` 转换和回写均受全局 pause/人工接管状态约束。它仅提交 `greeting` 到 MIC Outbox，等待 `sent`/`failed` 状态后才回写平台 message ID。`uncertain`、`requires_human_review`、缺少 gateway job ID、缺少平台 message ID或其他含糊结果都需人工对账，不能重建正文后重新发送。每条任务的 MIC 幂等键稳定派生自 CRM task ID。

导入的附件只包含受限元数据：最多 20 个项目，每项只含文件名、媒体类型和大小；不下载或传输附件正文、URL、凭据或附件内容。

### 迁移、备份与回滚

`0001_initial → 0002_message_history` 已在实时 MIC 数据库一致性备份副本验证：10 conversations、10 messages、1 Outbox 记录保留；10 个旧 conversation 的 `history_complete=false`。原运行数据库未在这项验证中迁移。上线迁移前，仍须用受控备份和批准的发布流程操作。

MIC 网关数据库、浏览器 profile 和 `crm-bridge/checkpoints.sqlite3` 位于 `MIC_APP_DATA_DIR`。迁移/升级前停止 MIC Gateway、bridge daemon、outbound Worker；备份整个数据目录并保持加密、ACL 与仓库隔离。迁移后使用当前版本执行 Alembic migration，验证 MIC health/status 和 CRM 只读计数，再启动计划任务。

回滚时停止 MIC bridge 和 Worker，保持 `FUSANHE_OUTBOUND_PAUSED=true`，回退相关代码并保留已导入记录、审计、bridge 检查点和 outbound 对账记录。不得为回滚删除 CRM conversation/message/Lead；确需恢复数据库时使用经过验证的一致性备份。

截至 2026-09-24，已通过隔离与离线测试；完整 MIC 历史、指定目标身份和真实发送仍未现场验证。本记录不构成真实渠道已接通或已成功发送的声明。

## 备份与恢复演练

创建备份：

```bash
./scripts/backup.sh
```

目录必须包含 `database.sql`、`espocrm-data.tgz`、`git-commit.txt` 和 `SHA256SUMS`。复制到异地加密存储后抽查：

```bash
cd backups/YYYYMMDD-HHMMSS
shasum -a 256 -c SHA256SUMS
```

恢复只能在隔离环境先演练：

```bash
./scripts/restore.sh backups/YYYYMMDD-HHMMSS
```

脚本会在停服务和覆盖卷之前强制校验清单。恢复后执行 `docker compose ps`、`make check`、登录只读抽查客户/会话/草稿数量，并确认停发开关仍为 true。

## 发布与回退

发布前必须通过 CI 的 Spec、Python、PHP 和 Android 四类门禁，并先创建完整备份。数据库元数据变更使用 EspoCRM rebuild，不手工改 vendor/core。

若发布失败：立即保持停发，停止新版本服务，恢复上一个 Git 版本；涉及数据库或持久卷变化时使用发布前备份恢复。完成健康检查后再开放内部用户，渠道开关仍不得随应用回退自动开启。

## 敏感信息事件

若 Token、备份或客户信息疑似泄漏：先保持停发并撤销相关 Agent 凭证，轮换引导 Token和所有受影响账户；保留请求 ID、时间、Agent key 和操作类型作为审计证据，但不得在事件记录中复制泄漏内容。
