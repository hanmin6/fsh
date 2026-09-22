# Alibaba Messenger 与福三和 CRM 集成设计

日期：2026-09-21

状态：已获用户确认，待实施计划

范围：`G:\FSH\alibb\alibaba_messenger` 与 EspoCRM 消息、客户和问候流程集成

## 1. 目标

将现有 Alibaba Messenger Playwright 服务接入福三和 CRM，形成以下闭环：

1. 首次导入阿里国际站的全部会话及全部文字历史。
2. 全量完成后每 5 分钟同步新增会话和新增消息。
3. 可靠识别并关联现有客户；无法可靠匹配时自动创建 Lead。
4. 根据会话上下文生成询盘进度问候和国家节假日问候。
5. 第一阶段由业务员批量审核候选问候，批准后才生成真实发送任务。
6. `alibb` 领取已批准任务、在阿里页面发送并将结果回写 CRM。
7. 全流程具备幂等、中断续传、停发、限额、审计和异常暂停能力。

## 2. 明确不在本次范围内

- 不修改已经可用的阿里官方 OAuth、Token 回调或 `api.fsh.digital` 回调链路。
- 不接入商品、订单或 RFQ 官方 API。
- 第一阶段不抓取或下载图片、文件、语音、视频和产品卡片等附件。
- 不把阿里系统提示作为 CRM 客户消息展示。
- 不自动批准问候草稿。
- 不修改 EspoCRM core、vendor 或镜像内原始文件。

CRM 已有的 `ExternalMessage.attachmentMetadata` 保留为后续附件扩展点。本次遇到附件时不伪造正文、不下载文件，也不阻塞同一会话的文字同步。

## 3. 架构与职责边界

```text
阿里国际站页面
       ↕
Alibaba Messenger 执行端（alibb）
       ├─ 全量枚举会话和历史
       ├─ 每 5 分钟执行增量读取
       ├─ 领取并执行 CRM 已批准的发送任务
       └─ 上报登录、验证码、风控、页面变化和发送结果
       ↕
福三和 CRM
       ├─ 会话、消息、ExternalIdentity、Lead 和客户关系
       ├─ 历史回填与增量入库规则
       ├─ 上下文分析与候选问候生成
       ├─ 本地结构化节假日日历及人工覆盖
       ├─ 批量审核、发送冷却、每日限额和停发开关
       └─ 状态机、审计、失败分类和重试
```

边界原则：

- `alibb` 是平台传输和浏览器执行端，不决定发送对象、发送时机或最终文案。
- CRM 是业务数据和业务决策的唯一来源。
- CRM 不保存阿里浏览器 Cookie，也不直接控制阿里网页。
- 阿里 Profile、Token、截图和本地同步数据库不进入 Git。
- OAuth 回调与 Messenger 集成相互独立，回调可用性不阻塞本设计。

## 4. alibb 组件设计

在现有 `alibaba_messenger` 能力外增加以下边界清晰的组件：

### 4.1 ConversationEnumerator

- 遍历阿里会话列表全部分页，直到明确到达末页。
- 不再受当前单页和 `limit <= 100` 的限制。
- 每条会话至少提取：`inquiryId`、买家名称、国家、列表状态、未读数、创建时间、更新时间。
- 优先提取稳定的阿里买家 ID、买家资料链接或页面数据属性。
- 分页终止同时检查“无下一页”和“本页标识已出现”，防止页面异常造成死循环。

### 4.2 HistoryReader

- 打开单个询价会话并加载全部历史。
- 只输出买家正文、卖家正文和首条询盘正文。
- 系统提示不进入消息时间线；需要保留时写入同步审计摘要。
- 将页面日期分隔符与消息时间组合成完整时间。
- 无法恢复完整日期时保留 `sourceTimestampRaw`，并标记时间可信度为 `low`，不得静默伪造精确时间。
- 优先读取 DOM 中的稳定消息 ID；不存在时生成稳定指纹。

### 4.3 SyncStateStore

使用本地 SQLite 保存非业务性的同步状态：

- 同步作业 ID 和模式（`backfill` 或 `incremental`）。
- 当前分页、当前 `inquiryId`、消息批次序号。
- 已完成会话、最近成功时间、重试次数和最后错误分类。
- 已发送 CRM 批次的幂等键。

SQLite 文件位于 Git 忽略目录。业务消息正文仍以 CRM 为准，本地状态库不作为业务档案。

### 4.4 CrmGateway

- 使用每个 Agent 独立的凭据访问 CRM。
- 推送会话和消息批次。
- 注册 Agent、发送心跳、领取发送任务、标记发送中并回写结果。
- 所有请求带请求 ID、客户端版本和本地时间。
- 网络失败采用有限指数退避；业务冲突不盲目重试。

### 4.5 OutboundWorker

- 只消费 CRM 已批准且属于 Alibaba 渠道的真实任务。
- 使用 CRM `idempotencyKey` 作为最高优先级防重键。
- 根据 `inquiryId` 定位目标，`buyerName` 仅作为辅助校验。
- 发送后必须验证页面出现正文一致的新卖家气泡。
- 能取得平台消息 ID时回写真实 ID；无法取得时回写稳定浏览器回执 ID并注明 `bodyMatch` 验证方式。
- 未出现匹配气泡时不得报告成功。

## 5. CRM 同步接口

新增版本化的 Alibaba 同步接口，使用 Agent 独立凭据，不复用普通用户登录，也不继续使用带有 `mock` 含义的入库路由。

建议路由：

```text
POST /api/v1/Fusanhe/alibaba/sync
```

单次请求处理一个会话快照和不超过 100 条消息：

```json
{
  "agentKey": "guangzhou-alibaba-01",
  "requestId": "uuid",
  "accountHandle": "default",
  "syncMode": "backfill",
  "jobId": "uuid",
  "batchNo": 1,
  "finalBatch": false,
  "conversation": {
    "inquiryId": "13907077489",
    "buyerExternalId": null,
    "buyerName": "Buyer Name",
    "country": "MY",
    "subject": "Inquiry subject",
    "sourceStatus": "待回复",
    "unreadCount": 1,
    "createdAtRaw": "2026-09-01 10:00",
    "updatedAtRaw": "2026-09-21 11:24"
  },
  "messages": [
    {
      "externalId": "dom-id-or-stable-fingerprint",
      "direction": "inbound",
      "body": "Message body",
      "translatedBody": "",
      "sentAt": "2026-09-21 03:24:00",
      "sourceTimestampRaw": "11:24",
      "timestampConfidence": "high",
      "sourceSequence": 12,
      "messageType": "chat"
    }
  ]
}
```

接口要求：

- 以 `accountHandle + inquiryId` 幂等创建或更新会话。
- 以 `conversation + externalId` 和内容指纹双重防重。
- 每个批次在数据库事务内处理。
- 返回创建、更新、忽略和失败数量，以及逐条稳定错误码。
- 同一个 `requestId` 重放时返回原结果。
- `backfill` 模式不触发草稿、问候、未读累加或发送任务。
- `incremental` 模式完成后才按最新有效消息更新会话状态。

## 6. 全量回填

### 6.1 工作流程

1. 人工启动一次全量作业。
2. `ConversationEnumerator` 获取全部分页。
3. 每个会话调用 `HistoryReader` 获取完整文字历史。
4. 消息按时间顺序、每批最多 100 条推送 CRM。
5. CRM 返回成功后才提交本地检查点。
6. 单个会话失败不终止整体作业，进入失败队列单独重试。
7. 全部会话完成后生成对账报告，再切换到增量模式。

### 6.2 幂等标识

- 会话键：`Alibaba + accountHandle + inquiryId`。
- 消息优先使用平台 DOM ID。
- 无 DOM ID 时使用 `inquiryId + direction + sourceTimestampRaw + normalizedBody + sourceSequence` 的 SHA-256 指纹。
- Lead 和 ExternalIdentity 分别使用稳定身份键或询价会话键防重。
- 重复执行同一全量作业不得增加会话、消息或 Lead 数量。

### 6.3 历史状态计算

- 最后一条有效消息来自买家：会话状态设为 `pending`。
- 最后一条有效消息来自卖家：会话状态设为 `replied`。
- 未读数使用阿里当前会话列表值，不按历史入站消息数量累加。
- 历史卖家消息直接保存为已发送消息，不反向创建 `OutboundTask`。
- 系统提示只计入同步审计统计，不计入最后消息和状态判断。

## 7. 增量同步

- 全量对账通过后，每 5 分钟运行一次。
- 优先扫描列表中更新时间变化、出现未读或新出现的会话。
- 对变化会话读取历史末尾；CRM 幂等层负责过滤已存在消息。
- 增量批次全部写入完成后，再更新会话状态、最后消息、未读数和同步时间。
- 登录失效、验证码、风控或页面变化时停止同步和发送，但保留待执行检查点。
- 异常解除后从最后成功检查点继续，无需重新全量导入。

## 8. 客户身份与 Lead

匹配优先级：

1. 稳定阿里买家 ID精确匹配。
2. 邮箱精确匹配且唯一。
3. 手机号精确匹配且唯一。
4. 已确认 ExternalIdentity 映射。

仅有买家名称和国家时不足以自动合并到已有正式客户，避免同名误合并。

没有可靠匹配时：

- 自动创建一个 Lead。
- 写入来源 `Alibaba`、买家名称、国家、询价单号和关联 ExternalIdentity。
- 如果没有稳定买家 ID，以询价会话作为临时身份边界，不跨询价自动合并。
- 后续取得稳定身份或人工确认后，可把多个会话关联到同一 Lead、Contact 或 Account。

## 9. CRM 数据模型调整

### 9.1 现有实体扩展

`ExternalConversation`：

- `sourceCreatedAtRaw`
- `sourceUpdatedAtRaw`
- `lastSourceSyncAt`
- `backfillCompletedAt`
- `syncError`

`ExternalMessage`：

- `sourceTimestampRaw`
- `timestampConfidence`：`high`、`medium`、`low`
- `sourceSequence`
- `messageType`：首期使用 `initialInquiry`、`chat`

`OutboundTask`：

- 领取载荷补充 `channelType`、`buyerName`、`inquiryId`、`triggerType`、`campaignId`。
- 结果补充 `receiptId`、可选 `platformMessageId`、`verificationMethod`。

`AutomationAgent`：

- 独立凭据哈希、凭据状态、最后使用时间和版本。
- 每日自动问候发送计数及重置日期。

### 9.2 新增问候实体

`FusanheGreetingRule`：

- 类型：`progress`、`holiday`。
- 启用状态、适用国家、节日代码、跟进天数、冷却期、每日上限。
- 模板、AI 提示、是否需要批准；第一阶段固定为需要批准。

`FusanheGreetingCampaign`：

- 规则、国家、节日、目标日期、状态、候选数、批准数、排除数和发送统计。
- 用于批量预览、逐个排除和批量批准。

`AIReplyDraft` 扩展：

- `triggerType`：`manual`、`progress7`、`progress14`、`progress30`、`holiday`。
- `triggerKey`：保证同一会话和触发事件只生成一份候选。
- `campaignId`：关联问候批次。

## 10. 询盘进度问候

触发规则：

- 卖家最后一次回复后，买家持续无新消息时，在第 7、14、30 天生成候选。
- 每个阶段最多生成一次。
- 买家回复、会话关闭、人工接管或第三次跟进完成后停止。
- 已存在等待审核或待发送问候时不重复生成。

生成上下文：

- 询盘主题、产品、国家、建议语言。
- 最近有效对话和上一次卖家回复。
- 已确认客户资料。
- 已审核知识中的品牌语气、业务约束和相关产品信息。

自动文案不得承诺价格、库存、交期、折扣、认证、付款条件、质量赔偿或其他未经人工确认的商业条件。

## 11. 节假日问候

### 11.1 日期来源

- 使用本地结构化国家节假日日历，不通过知识库检索日期。
- 自动覆盖 CRM 中买家所属的全部受支持国家。
- 默认仅启用主要公共节假日。
- CRM 管理员可停用节日、覆盖名称、调整触发日期和模板。
- 日历数据随应用版本更新并保留版本号，保证历史可追溯。

### 11.2 文案来源

- 知识库只提供品牌语气、禁用表达、产品背景和已批准模板。
- 宗教适用性不明确时使用中性公共节日文案。
- 每个“身份 + 节日 + 年份”最多生成一次。
- 节日前后与询盘进度问候冲突时合并为一条，节假日问候优先，避免短期重复打扰。

## 12. 批量审核与发送限制

第一阶段流程：

1. 定时规则生成 Campaign 和候选 AIReplyDraft。
2. 业务员批量预览。
3. 可排除单个买家或编辑单条文案。
4. 批量批准后才创建 OutboundTask。
5. `alibb` 按任务领取协议顺序发送。

限制：

- 每个阿里账号每天最多发送 30 条自动问候。
- 人工普通回复不计入自动问候额度。
- 同一买家执行跨规则冷却，避免节日和进度问候密集发送。
- 全局 `FUSANHE_OUTBOUND_PAUSED=true` 时任何真实任务都不能领取。
- 第一阶段没有自动批准；未来仅能按具体规则显式开启低风险自动发送。

## 13. 发送任务与成功判定

领取任务载荷：

```json
{
  "id": "task-id",
  "idempotencyKey": "sha256",
  "channelType": "Alibaba",
  "buyerName": "Buyer Name",
  "inquiryId": "13907077489",
  "body": "Approved final text",
  "triggerType": "holiday",
  "campaignId": "campaign-id",
  "claimExpiresAt": "2026-09-21 10:00:00"
}
```

发送成功必须同时满足：

- 任务属于当前 Agent，且未被取消或过期。
- 全局停发关闭，Agent 在线并具备 Alibaba 能力。
- 当日自动问候额度未耗尽。
- `idempotencyKey` 未成功执行过。
- 页面发送后出现正文一致的新卖家气泡。

成功回写包含：

- `receiptId`：始终必填，稳定且幂等。
- `platformMessageId`：能够从页面取得时填写。
- `verificationMethod`：`platformId` 或 `bodyMatch`。
- `sentAt`、客户端版本和请求 ID。

仅点击按钮、按下回车或生成截图都不足以判定发送成功。

## 14. 异常分类

| 异常 | Agent 状态/任务处理 |
| --- | --- |
| 登录过期 | `loginExpired`，停止同步和领取，等待人工登录 |
| 验证码 | `captcha`，停止该账号自动操作 |
| 平台风控 | `riskControl`，停止该账号全部自动发送 |
| 页面结构变化 | `pageChanged`，保存脱敏诊断信息并停止自动发送 |
| 买家或询价单不存在 | 任务进入人工处理，不执行三次盲目重试 |
| 网络或页面加载超时 | 有限重试，超过次数后保留可恢复失败状态 |
| CRM 暂时不可达 | 本地检查点保留，指数退避后重试 |
| 达到每日上限 | 不再领取自动问候，次日重置 |

失败分类必须进入 AutomationAudit。截图路径仅保留在执行端，不通过公开接口暴露本机路径。

## 15. 安全要求

- 每个 Agent 使用独立、可撤销、可轮换的凭据；CRM 只保存凭据哈希。
- `alibb` 的 HTTP API 增加认证，生产环境关闭 `/api/debug/*`。
- App Secret、Agent Secret、Token 和 Cookie 从源码移除，使用环境变量或 Windows 安全凭据存储。
- 已出现在源码中的现有凭据在首次正式提交前完成轮换。
- 日志默认隐藏正文、Cookie、Token、客户联系方式和完整页面内容。
- 所有 CRM 同步请求限制批次大小、正文长度和总请求体大小。
- 所有写接口记录请求 ID、Agent、目标实体、结果和错误分类。

## 16. 测试设计

### 16.1 alibb 离线测试

- 多页会话枚举、末页终止和重复页防循环。
- 完整历史加载、日期分隔符归一化和低可信时间处理。
- 买家、卖家、首条询盘和系统提示分类。
- DOM ID提取和指纹稳定性。
- SQLite 检查点、中断恢复和批次重放。
- CRM Gateway 的认证、超时、重试和错误分类。
- 发送后的新气泡匹配、正文不匹配和无气泡失败。
- 登录失效、验证码、风控和页面变化状态上报。
- 每日 30 条自动问候限制。

### 16.2 CRM 离线与运行时测试

- Backfill 不增加历史未读、不生成草稿、不生成任务。
- 重复 Backfill 不增加会话、消息、ExternalIdentity 或 Lead。
- Incremental 按最后一条有效消息设置 `pending` 或 `replied`。
- 历史卖家消息保存为发送记录但不创建 OutboundTask。
- 稳定身份唯一匹配和无匹配自动创建 Lead。
- 7、14、30 天触发、停止条件和触发幂等。
- 国家节日匹配、管理员覆盖、年度防重和节日/进度合并。
- Campaign 批量批准、单条排除、编辑和审计。
- 独立 Agent 凭据、任务所有权、停发和异常状态阻断。
- 成功回执幂等、终态错误不盲目重试、瞬态错误有限重试。

### 16.3 分阶段联调

1. 固定 HTML/JSON 样本离线解析。
2. CRM Docker 环境连接 Mock alibb。
3. 少量真实会话只读导入，不发送。
4. 重复导入并验证零重复。
5. 执行全部历史回填并生成数量对账。
6. 开启每 5 分钟增量同步。
7. 人工批准一条测试问候并验证单次真实发送。
8. 开放正式的批量审核问候流程。

## 17. 验收标准

- 阿里全部可访问会话及全部可读取文字历史完成回填。
- 单个失败会话可重试，全量任务中断后可续传。
- 同一全量任务重复执行不会产生重复数据。
- 新会话和新消息在正常登录状态下约 5 分钟内进入 CRM。
- 系统提示不进入客户消息时间线。
- 无可靠客户匹配时只创建一个幂等 Lead，不创建重复正式客户。
- 最后一条买家或卖家消息正确决定会话状态。
- 每个批准任务最多真实发送一次。
- 发送成功有平台 ID或正文气泡匹配证据。
- 首期不存在自动批准和无人审核发送。
- 每个阿里账号每天最多发送 30 条自动问候。
- 附件不导入，但现有扩展字段不受破坏。
- 凭据、浏览器 Profile、截图和客户数据不进入 Git。

## 18. 上线顺序

1. 先完成密钥外置、独立 Agent 鉴权和调试接口关闭。
2. 完成同步契约、CRM 入库和离线解析测试。
3. 运行少量只读导入并确认客户匹配结果。
4. 执行全量回填和对账。
5. 开启 5 分钟增量同步。
6. 完成单条人工批准真实发送验收。
7. 上线进度问候和节假日 Campaign 的批量审核。
8. 根据运行数据另行评审低风险规则自动发送，不在本设计中默认开启。
