# Muse Code + CRM MCP 接口

本阶段实现的是 CRM 侧的稳定 HTTP 边界。MCP server 后续只需要把下面三个
HTTP 操作包装成 MCP tools；Muse Code 不直接访问 EspoCRM 的通用 CRUD，也不
直接访问数据库。

## Agent 认证

先用现有 `/Fusanhe/agent/register` 注册一个 capability 包含 `MuseCRM` 的
Agent，例如 `muse-crm-01`。注册时使用服务端环境中的引导 Token，返回的
`agentToken` 只保存到 Muse Code 所在机器的密钥存储，不写入仓库、提示词或
CRM 记录。后续请求带：

```http
X-Agent-Key: muse-crm-01
X-Agent-Token: <one-time-issued-agent-token>
X-Request-Id: muse-<run-id>-<operation-id>
Content-Type: application/json
```

认证失败、过期或撤销时，接口统一返回 `403` 和安全错误码；不会透露 Agent
是否存在。

## MCP tool 映射

| MCP tool | CRM request | 用途 |
| --- | --- | --- |
| `crm_search_prospects` | `GET /api/v1/Fusanhe/muse/prospects` | 按 Muse sourceId、邮箱、电话或名称查找 |
| `crm_upsert_prospect` | `POST /api/v1/Fusanhe/muse/prospect` | 幂等创建/更新潜客及来源信息 |
| `crm_record_activity` | `POST /api/v1/Fusanhe/muse/activity` | 保存已生成或已发送的内容及结果 |

## Prospect upsert 示例

```json
{
  "sourceId": "muse-public-company-001",
  "sourceAccount": "muse-default",
  "sourceUrl": "https://example.com/company/001",
  "campaignKey": "seafood-2026-q4",
  "displayName": "Acme Foods",
  "company": "Acme Foods Ltd.",
  "email": "buyer@example.com",
  "country": "United Kingdom",
  "contactPolicy": "unknown",
  "notes": "公开页面上的采购方向；待人工核实"
}
```

同一个 `sourceAccount + sourceId` 始终对应同一个 CRM `Lead` 和
`ExternalIdentity`。已经被人工确认成 Account、Contact 或其他 Lead 的身份
不会被 Muse 覆盖。

## Activity 示例

```json
{
  "sourceId": "muse-public-company-001",
  "sourceAccount": "muse-default",
  "channelType": "Email",
  "channelAccountId": "sales-default",
  "conversationExternalId": "muse-campaign-001-company-001",
  "messageExternalId": "muse-message-0001",
  "direction": "outbound",
  "deliveryStatus": "queued",
  "subject": "Product inquiry",
  "body": "Hello, we noticed your public sourcing request...",
  "sentAt": "2026-10-01T08:00:00Z"
}
```

`queued` 只表示内容已进入 CRM；接口不会发信。发送器实际发出后用相同的
`messageExternalId` 再提交 `sent` 或 `delivered`，CRM 会幂等更新消息和潜客
最近触达时间。相同消息 ID 如果正文不同，会返回 `409 conflict`。

`optedOut` 或 `restricted` 会永久保留更严格的联系策略，并拒绝新的出站
activity。人工或合规流程解除限制不属于 Muse Agent 的权限。

## Muse Code 侧接入方向

MCP server 可以是本地 stdio 进程，也可以是远程 HTTP MCP server。MCP tool
内部调用上述 CRM REST 接口；CRM Agent token 只放在 MCP server 的环境变量
或密钥存储中。Muse 的模型输出、浏览器页面和完整运行日志不自动写入 CRM，
只有明确提交的客户字段和 activity body 会被保存。

## 已提供的 stdio MCP 连接器（2026-10-02）

`integrations/muse_crm_mcp.py` 使用 Python 3 标准库，无额外依赖，暴露上表三个
MCP tool。使用客户端的 MCP 设置添加 stdio server：

```json
{
  "mcpServers": {
    "fusanhe-crm": {
      "command": "python3",
      "args": ["/path/to/fsh/integrations/muse_crm_mcp.py", "--config", "/private/path/muse-crm.json"]
    }
  }
}
```

私有 JSON 配置包含 `CRM_API_URL=https://gzfusanhesp.com/api/v1`、
`FUSANHE_AGENT_KEY`、`FUSANHE_AGENT_TOKEN` 三个字段，必须使用实际发行的 Agent token。
Unix 权限 600；Windows 用当前用户 ACL。配置文件和 token 不提交 Git。
Windows 客户端的 command 可以使用 Python 可执行文件绝对路径。

连接器拒绝远程明文 HTTP、URL 内嵌凭据和重定向，不自动重试写请求。
MCP tool 的记录操作不触发平台发送。Muse 客户端仍需安装并加载此 MCP 设置；
服务端检查成功不等于客户端已连接，也不消耗或迁移 Muse 客户端的免费模型额度。
