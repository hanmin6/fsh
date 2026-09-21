# Data Model: 福三和 CRM 全系统基线

## Ownership

EspoCRM/MariaDB 是服务端系统记录。Android 本地数据是按当前用户权限保留的可重建投影，不是独立真相源。

## Customer Identity

### Customer (`Account`, `Contact`, `Lead`)

- 属性：名称、公司、邮箱、电话、国家、负责人、可见范围。
- 关系：可有多个外部身份、会话、询价、报价和订单。
- 校验：邮箱和电话先标准化；冲突线索不自动合并。

### External Identity

- 属性：渠道、平台用户 ID、显示名、公司、邮箱、电话、国家、匹配状态和依据。
- 关系：可关联一个 Account、Contact 或 Lead，被会话引用。
- 状态：`pending` → `linked` 或 `customerCreated`；关联变更必须审计。

## Conversation and Reply

### External Channel

- 属性：类型、启用状态、连接状态、最后同步时间、不含明文密钥的配置引用。
- 类型：`Alibaba`、`MadeInChina`、`Website`、`Email`、`WhatsApp`、`Other`。

### External Conversation

- 属性：渠道 ID、外部会话 ID、外部用户 ID、客户关联、负责人、未读数、收发时间、SLA 指标。
- 唯一性：`channelId + externalId` 唯一。
- 主流状态：`new` → `pending` → `waitingApproval` → `readyToSend` → `sending` → `sent`。
- 异常/终止：可进入 `failed`；授权用户可关闭已完成会话。

### External Message

- 属性：会话 ID、外部消息 ID、方向、正文、附件元数据、交付状态、受控原始摘要、内容哈希。
- 唯一性：`conversationId + contentHash` 唯一；稳定外部 ID 同样用于去重。
- 方向：`inbound` 或 `outbound`。

### AI Reply Draft

- 属性：会话、原始生成内容、当前草稿、意图、摘要、语言、缺失信息、置信度、风险、引用知识、审批人/时间。
- 状态：`generated` → `edited` → `approved` 或 `rejected`；成功发送后可进入 `sent`。
- 不变性：已批准记录不可删除，发送快照不随后续编辑变化。

### Outbound Task

- 属性：会话、草稿、渠道、载荷快照、幂等键、领取 Agent、领取到期、重试数、错误摘要、平台消息 ID。
- 唯一性：`idempotencyKey` 唯一；同一会话同时只允许一个活跃任务。
- 状态：`pending` → `claimed` → `sending` → `sent` 或 `failed`；未发送前可 `cancelled`。
- 重试：仅对确认未发送的暂时失败重试；不确定结果先对账。

## Knowledge and Execution

### Knowledge Document

- 属性：路径/来源引用、类型、校验值、大小、解析摘要/错误、审核状态、到期时间。
- 状态：`draft` → `approved` → `expired`。仅已审核且未到期内容可进入 AI 上下文。

### Automation Agent and Credential

- 属性：稳定 Agent ID、名称、渠道能力、状态、最后心跳、错误摘要、凭证版本/状态。
- 状态：`online`、`offline`、`loginExpired`、`captcha`、`pageChanged`、`riskControl`。
- 凭证：每 Agent 独立，只存哈希与必要标识，支持签发、轮换、撤销。

### Automation Audit

- 属性：事件类型、主体类型/ID、操作者或 Agent ID、请求 ID、时间、结果、脱敏摘要。
- 限制：不保存明文凭证、Cookie、完整私密载荷或不必要客户正文。

## Food-Trade

- **Product / Product Specification**: Product 是稳定商品身份；Specification 版本在同一产品内唯一，批准后受保护。
- **Certificate / Report**: 具有类型、范围、签发方、编号、有效期、文档和状态；`draft` → `approved` → `revoked/expired`。
- **Sample**: 关联客户和产品/规格，包含数量、追踪号、费用、反馈和跟进时间；必须从初始状态创建。
- **Inquiry / Quote / Quote Item / PI**: 从需求与缺失信息形成有版本的商务快照；接受后不可用通用 CRUD 改写。
- **Sales Order / Line / Shipment / Item**: 已接受报价幂等建单；多批交付的累计数不得超过订购量。

## Mobile Projection

### Session and Sync State

- 属性：用户 ID、授权范围、会话到期、同步游标、缓存版本、待重试操作和幂等键。
- 授权撤销或范围缩小后，本地受限数据不得继续可见。
- 服务端状态与权限优先于本地预测。
