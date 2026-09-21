# System Contracts: 福三和 CRM 全系统基线

## Ownership and Compatibility

- `custom/Espo/Custom/Resources/routes.json` 是自定义 HTTP 路由权威源。
- `custom/Espo/Custom/Tools/Fusanhe/Api/` 拥有请求校验、认证、授权和错误转换。
- `custom/Espo/Custom/Tools/Fusanhe/Connector/Connector.php` 拥有渠道适配契约。
- 不兼容变更必须新增版本路径或提供可验证迁移期，不静默破坏 Web、Android 或 Agent。

## Common HTTP Contract

- 业务用户使用 EspoCRM 会话或后续明确规格的移动认证；每个变更在服务端验证实体级与记录级权限。
- 客户端可传 `X-Request-Id`，系统在响应、日志和审计中关联同一值。
- Agent 基线现状使用 `X-Automation-Token`；目标是每 Agent 独立 Bearer 凭证。声明的 `agentKey` 必须与凭证归属一致。

### Target envelopes

```json
{"data": {}, "meta": {"requestId": "req-..."}}
```

```json
{"error": {"code": "FUSANHE_STABLE_CODE", "message": "Safe summary", "details": {}, "retryable": false}, "meta": {"requestId": "req-..."}}
```

- `400` 输入无效；`401` 凭证无效/过期/撤销；`403` 无权；`404` 不存在或不可见；`409` 幂等/状态/并发冲突；
  `422` 业务要求不完整；`429` 限流；`5xx` 服务失败且不暴露密钥或私密载荷。

## Route Families

### Inquiry, identity, conversation

- `POST /Fusanhe/mock/intake`: 幂等导入演示询盘，拒绝未知渠道。
- `GET /Fusanhe/identity/:id/candidates`: 仅返回当前用户可见候选与匹配依据。
- `POST /Fusanhe/identity/:id/link|create-customer`: 显式、幂等、可审计地确定客户身份。
- `POST /Fusanhe/conversation/:id/generate-draft|manual-draft`: 只保存草稿，不隐式批准或发送。
- `POST /Fusanhe/draft/:id/approve`: 保留批准快照，幂等创建一个发送任务。
- `POST /Fusanhe/conversation/:id/control|handoff`: 仅允许明确动作，保留负责人与语境快照。
- `GET /Fusanhe/conversation/:id/handoff-tasks`: 只读且按权限返回。
- `POST /Fusanhe/task/:id/cancel`: 仅取消未确认发送任务，已发送事实不回退。

### Execution agent

- `register`: 登记稳定 Agent 身份与能力；目标契约签发仅显示一次的独立凭证。
- `heartbeat`: 上报状态和脱敏错误，不修改任务。
- `claim`: 停发、凭证、在线状态和渠道能力均是领取门禁。
- `task/:id/sending`: 仅领取者可进入发送中，并再次校验停发。
- `task/:id/result`: 幂等回写；成功必须有平台消息 ID；不确定结果不盲目重试。

### Read-only, knowledge, food trade

- `GET /Fusanhe/dashboard|status|features`: 无副作用；前两者需权限；features 可见性不代表授权。
- `POST /Fusanhe/knowledge/scan`: 仅索引允许的只读目录，单文件失败不阻断其他文件。
- `product-spec`、`certificate`、`sample`、`quote`、`order`、`shipment` 动作路由是受保护状态迁移的唯一入口；
  通用 CRUD 不得伪造批准、接受或交付。

## Connector Contract

`Connector.php` 的七个方法是稳定边界：`fetchConversations`、`fetchMessages`、`acknowledgeMessage`、
`prepareReply`、`createOutboundTask`、`reportSendResult`、`healthCheck`。实现必须保留增量游标、去重、幂等、
有界重试、不确定结果对账和脱敏健康状态。

## Mobile Contract

- 列表提供稳定排序、不透明分页游标和服务端变更版本；变更请求支持客户端幂等键。
- DTO 未知枚举不崩溃，而映射为可见的 `unknown`/不支持状态并上报诊断。
- 权限或会话失效后受限缓存不继续显示。WebSocket 只做失效/刷新信号，业务数据仍经授权同步契约获取。
