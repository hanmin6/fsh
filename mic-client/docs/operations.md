# Made-in-China Gateway Windows 运维手册

本服务面向一个 Made-in-China 供应商账号，运行在长期在线的 Windows 用户会话中。CRM 通过本机 API 查询订单、询盘和消息；Agent 只能提交问候、确认收到、节日祝福和非商业跟进。报价、价格、付款、交期、库存、合同、退款和争议内容会进入人工审核，不会自动发送。

## 1. 安全边界与当前限制

- 服务监听 `0.0.0.0:8787`，但 Windows 防火墙只应放行本机和明确的可信局域网地址。不要直接暴露到公网；远程访问应使用 VPN 或 TLS 反向代理。
- 浏览器使用独立目录 `MIC_APP_DATA_DIR\browser-profile`，不得复用个人 Chrome 配置。
- Made-in-China 当前把关键登录信息保存在浏览器进程级会话 Cookie 中。Windows 重启、任务重启或浏览器进程退出后，可能需要在服务打开的同一个 Chromium 窗口中重新登录。先运行 `browser-login` 再关闭窗口，不能保证后续服务仍保持登录。
- 当前账号没有历史订单，因此已验证“订单空分页”，未观察到非空订单 JSON。第一笔订单出现时，适配器会以 `order_list_nonempty_unreviewed` 失败关闭，避免错误映射金额或状态；届时应重新执行脱敏发现并发布订单解析更新。
- 已验证询盘列表和初始询盘消息读取。聊天组件在发现时曾出现明确初始化失败态；此状态不会被当成空消息，也不会尝试发送。
- 线上发送冒烟测试默认禁用，本次安装不应运行 `--live-send`。

## 2. 安装

以专用 Windows 用户登录。示例目录：

```powershell
$SourceDir = "C:\src\made-in-china"
$InstallDir = "C:\MadeInChinaGateway"
$AppDataDir = "G:\MadeInChinaGatewayData"
Set-Location $SourceDir
```

先检查安装计划，再执行：

```powershell
.\scripts\install-windows.ps1 -InstallDir $InstallDir -AppDataDir $AppDataDir -DryRun
.\scripts\install-windows.ps1 -InstallDir $InstallDir -AppDataDir $AppDataDir
```

脚本会创建独立虚拟环境、安装服务、安装 Playwright Chromium、在应用数据目录中执行 Alembic 迁移、设置用户级 `MIC_APP_DATA_DIR`，并把应用数据 ACL 限制为当前用户和本机管理员。应用数据目录不得位于源码树内。

若当前 PowerShell 尚未读取新的用户环境变量，先执行：

```powershell
$env:MIC_APP_DATA_DIR = $AppDataDir
```

## 3. API 密钥

分别为 CRM、Agent 和管理员创建最小权限密钥。密钥只显示一次，不要写入任务参数、源码或日志：

```powershell
& "$InstallDir\.venv\Scripts\python.exe" -m mic_gateway.cli create-api-key --name crm-prod-2026-09 --role crm_read
& "$InstallDir\.venv\Scripts\python.exe" -m mic_gateway.cli create-api-key --name agent-prod-2026-09 --role agent_send
& "$InstallDir\.venv\Scripts\python.exe" -m mic_gateway.cli create-api-key --name admin-prod-2026-09 --role admin
```

客户端使用请求头 `X-API-Key: mic_...`。轮换时先创建带新版本名称的密钥，更新调用方并验证，再在维护窗口撤销旧密钥；撤销前备份数据库并确保至少保留一个管理员密钥：

```powershell
& "$InstallDir\.venv\Scripts\python.exe" -m mic_gateway.cli revoke-api-key --name crm-prod-2026-08
```

## 4. 手动启动与登录

首次部署先手动启动，以便观察浏览器和登录状态：

```powershell
$env:MIC_APP_DATA_DIR = $AppDataDir
Set-Location $InstallDir
& ".\.venv\Scripts\python.exe" -m uvicorn mic_gateway.main:create_production_app --factory --host 0.0.0.0 --port 8787
```

服务会打开独立 Chromium。如果跳转到登录页，在这个窗口中完成登录并进入询盘后台；不要关闭窗口。调度器每 10 秒重新检查登录态，成功后自动恢复只读同步和 Outbox 处理。遇到 CAPTCHA 或验证页时，同样在该窗口人工完成。

开发或脱敏发现可使用：

```powershell
& "$InstallDir\.venv\Scripts\python.exe" -m mic_gateway.cli browser-login
& "$InstallDir\.venv\Scripts\python.exe" -m mic_gateway.cli discover --resource orders
& "$InstallDir\.venv\Scripts\python.exe" -m mic_gateway.cli discover --resource conversations
& "$InstallDir\.venv\Scripts\python.exe" -m mic_gateway.cli discover --resource messages
```

发现命令只用于维护契约，消息发现只打开指定会话，禁止发送。推广任何夹具前必须运行隐私扫描：

```powershell
rg -n -i "authorization|cookie|token|session|@|phone|mobile|address" "$AppDataDir\discovery"
```

## 5. 计划任务

确认手动启动正常后注册登录触发的交互式任务：

```powershell
.\scripts\register-task.ps1 -InstallDir $InstallDir -DryRun
.\scripts\register-task.ps1 -InstallDir $InstallDir
Start-ScheduledTask -TaskName MadeInChinaGateway
```

任务使用当前专用用户、`Interactive` 登录类型和 `AtLogOn` 触发器，最多重启三次。它不会把 API 密钥写入参数。由于浏览器需要人工登录，不要改成无人值守服务账号或后台 Session 0 任务。

## 6. 防火墙

CRM 与服务在同一电脑时无需新增入站规则，使用 `http://127.0.0.1:8787`。需要局域网访问时，以管理员 PowerShell 显式指定可信地址：

```powershell
.\scripts\configure-firewall.ps1 -RemoteAddress 127.0.0.1,192.168.10.0/24 -DryRun
.\scripts\configure-firewall.ps1 -RemoteAddress 127.0.0.1,192.168.10.0/24
```

脚本拒绝 `*`、`0.0.0.0/0` 和 `::/0`。

## 7. 启动检查与 API

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health/live
Invoke-RestMethod http://127.0.0.1:8787/health/ready
Invoke-RestMethod http://127.0.0.1:8787/v1/status -Headers @{ "X-API-Key" = $AdminKey }
```

常用读取接口：

- `GET /v1/orders`
- `GET /v1/orders/{id}`
- `GET /v1/conversations`
- `GET /v1/conversations/{id}/messages`
- `GET /v1/jobs/{id}`

游标由响应的 `next_cursor` 返回；调用方不得解析或修改游标。

Agent 提交消息：

```powershell
$body = @{
    idempotency_key = "crm-event-20260921-001"
    intent = "greeting"
    content = "Hello, thank you for contacting us."
    caller_reference = "crm-event-001"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8787/v1/conversations/$ConversationId/messages" `
    -Headers @{ "X-API-Key" = $AgentKey } `
    -ContentType "application/json" `
    -Body $body
```

每个业务事件必须使用稳定且唯一的 `idempotency_key`。返回 `requires_human_review` 时必须交给人工，不得换措辞自动重试。`uncertain` 表示点击后缺少确认，系统不会自动二次发送。

管理员可请求同步：

```powershell
Invoke-RestMethod `
    -Method Post `
    -Uri http://127.0.0.1:8787/v1/admin/sync `
    -Headers @{ "X-API-Key" = $AdminKey } `
    -ContentType "application/json" `
    -Body '{"resource":"all"}'
```

## 8. 状态处理

- `healthy`：登录、数据库和同步新鲜度正常。
- `degraded`：同步过期、站点暂时不可用或出现安全错误码。
- `operator_action_required`：需要登录或人工完成验证；自动读取和发送均暂停。
- `site_contract_error`：站点结构与已审查契约不一致；禁止把未知页面当成空数据。

登录丢失或 CAPTCHA 恢复步骤：

1. 查看服务打开的专用 Chromium，不要另开个人 Chrome。
2. 完成登录或验证并进入询盘后台。
3. 等待 10 秒后再次查询 `/v1/status`。
4. 仍异常时停止任务，手动启动服务观察终端错误；不要删除浏览器配置或自动重试发送。

## 9. 备份、升级、回滚与停机

干净停机：

```powershell
Stop-ScheduledTask -TaskName MadeInChinaGateway
```

确认 Chromium 和 Python 进程已退出后，再备份整个 `$AppDataDir`。该目录包含数据库和登录资料，备份必须继承同等 ACL，不得上传到公开云盘。至少保留升级前一份离线备份。

升级：

1. 停止任务并备份 `$AppDataDir`。
2. 在新源码版本上重新运行 `install-windows.ps1`；脚本会更新包、浏览器和数据库迁移。
3. 手动启动并验证 `/health/live`、登录、`/v1/status` 和只读查询。
4. 再启动计划任务。

回滚：停止任务，恢复旧应用数据备份，使用旧源码版本重新运行安装脚本，然后手动验证。数据库发生向前迁移后，不要只降级 Python 包而保留新数据库。

诊断保留：仅保留脱敏后的发现文件和安全错误码。不要在工单或日志中复制 Cookie、Authorization、完整客户正文、客户邮箱或手机号。

## 10. 验收记录（历史基线：2026-09-21）

以下数据是 2026-09-21 的网关历史验收快照，不代表本次 MIC→CRM 集成状态；本次状态见第 12 节。

本记录只包含结果和合成测试标识，不包含客户数据或凭据。

| 项目 | 结果 | 证据/备注 |
| --- | --- | --- |
| 软件版本 | 已确认 | `0.1.0` |
| 数据库迁移 | 已确认 | `0001_initial` |
| 完整非生产测试与覆盖率 | 通过 | 120 passed，2 skipped；总覆盖率 82%；`api/auth.py` 90%、`messaging/outbox.py` 92%、`policies/messages.py` 98% |
| Ruff / mypy | 通过 | Ruff 无错误；mypy 检查 36 个源码文件无错误 |
| 适配器契约测试 | 通过 | 8 passed |
| 完整假适配器验收流 | 通过 | 5 passed；包含合成标识 `acceptance-1`、权限拒绝、人工审核、幂等并发、登录丢失、未知发送和重启恢复 |
| 开发机只读 live smoke | 通过 | 1 passed；确认登录标记、空订单响应和询盘列表；同一浏览器进程内执行 |
| 真实测试会话发信 | 未执行 | 尚未提供明确指定的测试会话；为避免误发，未运行 `--live-send` |
| 重启恢复 | 通过（隔离数据库） | 处于 `sending` 的任务重启后变为 `uncertain`，不会自动重发 |
| 操作员退出/重新登录恢复 | 部分通过 | 已验证同进程人工登录后只读同步；目标机上的主动退出、`operator_action_required` 和重新登录恢复仍待验收 |
| Windows 计划任务与防火墙 | 脚本验证通过，目标机待执行 | 4 项 DryRun 合约测试通过；尚未在长期在线目标机实际注册或开通规则 |

发布候选当前可以用于代码审查和目标机部署准备，但只有完成表中三个“未执行/待执行”项目后，才能签署生产验收。真实发信验收必须使用人工明确指定的测试会话，并同时提供 `--live-send`、`MIC_LIVE_TEST_CONVERSATION_ID` 和 `MIC_LIVE_TEST_RECIPIENT_LABEL`；缺少任一条件时测试会跳过，不得绕过保护。

## 11. CRM Bridge: Checkpoints, Conflicts, and ID Limits

The read-only CRM bridge keeps its checkpoint database under `MIC_APP_DATA_DIR\crm-bridge`. A CRM request is checkpointed only after a response confirms the matching `requestId`. If a request may have reached CRM but the reply was lost, the bridge retains its pending request and retries it with the same ID and payload.

If the MIC source changes before that pending request can be replayed, the bridge marks `pending_batch_conflict`, stops that import run, and leaves the source cursor unchanged. `status` displays the action code and pending CRM request ID. Do not remove the checkpoint database or start another import mode to work around this state.

Resolve the ambiguity only after checking the CRM `AutomationAudit` record for the exact request ID:

```powershell
python -m mic_gateway.crm_bridge.cli status
python -m mic_gateway.crm_bridge.cli resolve-pending conversations:once `
    --request-id "<requestId-from-status>" --verified-accepted
```

Use `--verified-accepted` only when the CRM audit confirms that exact request ID was accepted. The bridge then advances to the pending cursor; subsequent `once` sweeps reread MIC history and import newer source content. If the audit confirms the request was not accepted, clear the pending marker without advancing the cursor:

```powershell
python -m mic_gateway.crm_bridge.cli resolve-pending conversations:once `
    --request-id "<requestId-from-status>" --verified-not-accepted
```

If CRM audit state is unavailable or ambiguous, leave the pending record unchanged and ask the CRM operator to investigate. The CLI does not query or infer CRM audit acceptance itself. Both resolution options require the exact pending request ID and an explicit operator decision. Each decision is recorded locally with resource, request ID, outcome and timestamp only; the record contains no payload or buyer content, and `status` displays recent entries.

CRM external IDs are limited to 191 characters. MIC IDs longer than that are represented in CRM as the deterministic account-scoped alias `mic-sha256:<sha256(accountHandle + NUL + sourceId)>`; they are hashed rather than truncated. IDs already using the reserved `mic-sha256:` prefix are hashed too. The alias is stable for the account and original ID, but the raw long ID is not stored in bridge checkpoints or logs. Conversation subjects longer than 255 Unicode characters are clipped to 255 for CRM. A source ID that cannot be safely encoded or represented reports `source_identity_alias_unavailable`; that conversation is skipped, later conversations continue, and the checkpoint does not advance past the affected page.

## 12. MIC-to-CRM Backfill and Outbound Worker

### 配置与凭证

MIC 主服务和 CRM bridge 共用 `MIC_APP_DATA_DIR`。它必须位于源码树之外，并使用专用 Windows 用户 ACL；bridge 状态库位于 `MIC_APP_DATA_DIR\crm-bridge\checkpoints.sqlite3`。该目录同时含网关数据库、浏览器配置和桥接检查点，按敏感运行数据保护。

Bridge 从进程环境直接读取以下配置，不会自动读取项目 `.env`。在运行 bridge 命令和 Worker 的进程环境中设置：

| 变量 | 用途 |
| --- | --- |
| `MIC_APP_DATA_DIR` | 网关数据和 CRM bridge 检查点目录 |
| `MIC_GATEWAY_URL` | 本机网关地址，通常为 `http://127.0.0.1:8787` |
| `MIC_ACCOUNT_HANDLE` | 当前唯一 MIC 卖家账号标识，用于 CRM 账号范围 |
| `MIC_CRM_URL` | CRM API 根地址，默认 `http://127.0.0.1:8080` |
| `MIC_CRM_AGENT_KEY` | 注册到 CRM 的 MIC Agent key，默认 `mic-agent` |
| `MIC_CRM_READ_API_KEY` | MIC Gateway `crm_read` key，供历史导入和读取 |
| `MIC_CRM_SEND_API_KEY` | MIC Gateway `agent_send` key，供出向 Worker 调用 |
| `MIC_CRM_BOOTSTRAP_TOKEN` | CRM 的 `FUSANHE_AUTOMATION_TOKEN`，仅供显式 `register` |
| `MIC_CRM_AGENT_TOKEN` | CRM 注册后一次返回的 Agent token，供后续同步及 Worker 鉴权 |
| `MIC_CRM_ALLOW_REMOTE_HTTPS` | 仅在 CRM 使用经批准的远程 HTTPS 地址时设为 `true`；默认只允许 loopback |

分别创建最小权限 MIC key，并把明文只保存到受保护的部署密钥配置，不写入仓库、脚本参数、日志或工单：

```powershell
python -m mic_gateway.cli create-api-key --name crm-mic-read --role crm_read
python -m mic_gateway.cli create-api-key --name crm-mic-send --role agent_send
```

CRM 的 `FUSANHE_OUTBOUND_PAUSED` 应保持 `true`（未配置时默认也是 true）。`FUSANHE_AUTOMATION_TOKEN` 只用作 bridge 的 `MIC_CRM_BOOTSTRAP_TOKEN`，不得作为日常 Agent 凭证。

### 注册 Agent 与历史导入

在 MIC 项目的虚拟环境中运行命令。注册默认会旋转同一 Agent 的旧凭证；只有明确要保留既有凭证时才使用 `--no-rotate`。`register` 成功时 CRM Agent token 只输出一次，立即写入受保护的 `MIC_CRM_AGENT_TOKEN` 配置并清除 bootstrap token 环境变量：

```powershell
python -m mic_gateway.crm_bridge.cli register
```

先确认 MIC 网关登录和数据健康，再运行首次完整历史回填。`backfill` 只在每个会话的 `history_complete=true` 时导入；任何缺少完整标记或无法验证会话身份的记录都会失败关闭，不会把它当成空历史。只有完成授权现场验收后才运行：

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health/live
Invoke-RestMethod http://127.0.0.1:8787/health/ready
Invoke-RestMethod http://127.0.0.1:8787/v1/status -Headers @{ "X-API-Key" = $MicReadKey }
python -m mic_gateway.crm_bridge.cli backfill
```

回填成功后用 `once` 做一次增量扫描；持续读取更新可运行 `daemon`，默认每 60 秒扫描一次，短暂的 429/5xx/网络错误使用有上限的退避：

```powershell
python -m mic_gateway.crm_bridge.cli once
python -m mic_gateway.crm_bridge.cli daemon --interval 60
```

检查点只在 CRM 确认了同一 `requestId` 的接受响应后推进。用 `status` 查看游标、未完成批次、冲突码和最近的人工决策：

```powershell
python -m mic_gateway.crm_bridge.cli status
```

`status` 不显示密钥或导入正文。状态库保存检查点、请求 ID 和摘要；不要删除它来绕过失败，也不要同时运行两个导入进程。

若状态显示 `pending_batch_conflict`，先用精确 `requestId` 在 CRM `AutomationAudit` 中核对结果。只有审计明确确认接受时才能运行 `--verified-accepted`；明确未接受时才运行 `--verified-not-accepted`。审计缺失或结果不明时保持 pending 并升级处理，不猜测、不手改 SQLite、不重建检查点。两种人工决策都会记录在本地状态库中。

```powershell
python -m mic_gateway.crm_bridge.cli resolve-pending conversations:once `
    --request-id "<status 中的精确 requestId>" --verified-accepted
```

### 出向 Worker、全局停发与结果对账

完整历史与目标身份的现场门槛通过后，Worker 由 MIC 应用环境单独启动。它只领取 CRM 中已审批且 `executionMode=real` 的 MIC 任务；发送前再次向 CRM 标记 `sending`，由 CRM 的全局停发和人工接管校验作最后阻断。`agent_send` key 与 CRM Agent token 都必需：

```powershell
python -m mic_gateway.crm_bridge.run_worker --once
python -m mic_gateway.crm_bridge.run_worker --interval 30
```

`--once` 执行一轮，`--interval 30` 持续轮询并对可重试故障退避。出向 Worker 与 CRM API 服务进程分开运行；如需长期计划任务，需用同一专用用户会话配置并制定有序停机步骤。不要通过临时创建 CRM 任务验证生产发送。

`uncertain`、`requires_human_review`、网关 job ID 未落盘、CRM 回写缺少平台消息 ID或传输结果含糊时，Worker 会保留本地 task/key/job 对账记录或报告人工处置，不会重发。先在 MIC `/v1/jobs/{job_id}`、CRM `OutboundTask` 和 CRM `AutomationAudit` 间逐项核对，再由授权操作员处理。桥接状态只保存 task ID、MIC source ID、幂等 key、Gateway job ID、状态和时间戳，不保存已批准的消息正文。

历史入库只传附件元数据，不下载、保存或上传附件内容。`attachmentMetadata.items[]` 每项仅含 `name`（最多 255 字符）、`mediaType`（最多 127 字符或 null）和 `size`（非负整数或 null），最多 20 项；拒绝 URL、data URI、认证/Token 字段及额外字段。

### 登录、健康、备份迁移与回滚

网关须在专用 Windows 用户的交互式 Chromium 会话中登录，不复用个人 Chrome，不自动绕过 CAPTCHA 或验证。登录丢失时在网关打开的浏览器中人工恢复，然后确认 `/health/ready` 为 200、`/v1/status.session.state=healthy` 且会话同步 `fresh=true`、`failure_count=0`；Worker 对状态不满足条件的发送会停止。

升级或迁移前先停止 MIC 网关计划任务、桥接 `daemon` 和 outbound Worker，确认相关进程结束后备份整个 `MIC_APP_DATA_DIR`。该备份包含 SQLite WAL 数据库、浏览器登录资料和桥接检查点，必须加密、限制 ACL 并与仓库分开存放。迁移时将目录恢复到新主机上的源码树外部路径，设置相同环境变量和 ACL，在专用用户下按当前版本执行 Alembic migration，再启动网关并完成登录/健康/只读检查。保留升级前备份；不要仅降级程序包并保留新 schema。

CRM `0001_initial → 0002_message_history` 迁移已经在实时 MIC 数据库的一致性备份副本上验证，记录数量保持为 10 个 conversation、10 条 message 和 1 条 Outbox 记录；副本中 10 个旧 conversation 的 `history_complete` 均为 false。原运行数据库未在这项验证中迁移。这个迁移证据不表示平台历史或发送已通过现场验收。

回滚时停止 bridge 与 Worker、保持 `FUSANHE_OUTBOUND_PAUSED=true`，按部署流程回退 MIC/CRM 代码版本；保留导入的 conversation/message、审计记录、outbound 对账记录和检查点，不因回滚删除业务记录。确需退回旧数据库时只在有一致性备份且完成恢复验证后执行。完成只读健康检查后再恢复服务；真实发送仍需单独的指定目标验收。

截至 2026-09-24，MIC Python 3.12 全量离线套件为 **269 passed, 2 deselected**，Ruff 和 mypy 均干净；CRM MIC+Alibaba 离线契约 **39 passed/16 skipped**，PHP lint 通过、隔离 MIC+Alibaba runtime **16/16**，前端 **13/13**。完整 TradeMessenger 历史、指定目标身份和真实发送尚未现场验证，故不宣称已完成历史回填或真实发送。
