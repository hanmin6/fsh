# 后端接口映射说明（Android 客户端 → EspoCRM）

> 客户端当前为 UI 演示（Mock Repository），本文档说明每个页面在接入真实后端时需要的接口、
> 请求/响应字段与实时更新方式。后端为 EspoCRM 10.0.8，API 前缀 `http://localhost:8080/api/v1`，
> 认证方式建议：HTTP Basic（请求头 `X-Espo-Authorization: base64(user:pass)`）或后续 OAuth/Token。
>
> 已预留的 Retrofit 接口定义：`data/remote/api/CrmApiService.kt`；
> DTO 占位：`data/remote/dto/Dtos.kt`。

## 当前后端真实能力

本文后续部分包含目标接口设计。2026-09-19 时已经存在并通过验证的自定义接口如下：

| 功能 | 当前接口 | 状态 |
| --- | --- | --- |
| 询盘入库 | `POST /Fusanhe/mock/intake` | 可用，仍需业务 ACL |
| 生成 AI 草稿 | `POST /Fusanhe/conversation/{id}/generate-draft` | 可用 |
| 批准草稿 | `POST /Fusanhe/draft/{id}/approve` | 可用，有发送任务创建权限校验 |
| Dashboard | `GET /Fusanhe/dashboard` | 可用，只读 |
| 运行状态 | `GET /Fusanhe/status` | 可用，只读 |
| 知识扫描 | `POST /Fusanhe/knowledge/scan` | 可用，仍需业务 ACL |
| 执行端协议 | `/Fusanhe/agent/*` | Mock 闭环可用，仍使用共享 Token |
| 翻译 | 无 | 待开发 |
| Android 登录 Token | 无 | 待开发 |
| 消息实时订阅 | EspoCRM WebSocket 基础存在 | Android 尚未接入 |

Android 模拟器访问宿主机 CRM 时应使用 `http://10.0.2.2:8080/api/v1/`，真机应使用可访问的局域网或 HTTPS 地址，不能使用手机自身的 `localhost`。

## 通用约定

- **分页**：`GET /{entity}?offset=0&maxSize=20`，响应含 `total` 与 `list`。
- **筛选**：Espo `where` JSON 查询参数（`?where=[{"type":"equals","attribute":"assignedUserId","value":"..."}]`）。
- **排序**：`?orderBy=lastMessageAt&order=desc`。
- **领域模型映射**：DTO ↔ `domain/model` 的转换在真实 Repository 的 Mapper 中完成，UI 不感知。

---

## 1. 登录页（login）

| 项 | 说明 |
| --- | --- |
| 接口 | `GET /App/user`（校验当前凭证）或后端自定义 `POST /ActionLogin` |
| 请求 | Basic Auth 头（用户名/密码） |
| 响应 | `user.id`、`user.userName`、`user.name`、`user.roles`、`user.teams` |
| 客户端处理 | 成功后保存凭证于 EncryptedSharedPreferences（**严禁硬编码**），初始化 `SessionRepository` |

## 2. 工作台（dashboard）

| 项 | 说明 |
| --- | --- |
| 今日新增询盘 | `GET /ExternalConversation?orderBy=createdAt&order=desc`，客户端按 `createdAt ∈ 今日` 聚合；或后端提供报表 action `GET /ExternalConversation/action/dashboardStats`（推荐，一次返回计数） |
| 待回复 / 待审核 | `GET /ExternalConversation?where=[{"type":"in","attribute":"status","value":["Waiting","ToReview"]}]` 后本地计数 |
| 超时询盘 | 字段 `waitingMinutes` + `slaBreached`（后端定时任务计算写入） |
| 发送异常 | `GET /OutboundTask?where=[{"type":"equals","attribute":"status","value":"Failed"}]` |
| 最近客户 | `GET /Contact?orderBy=lastContactAt&order=desc&maxSize=3` |
| 最近询盘 | `GET /ExternalConversation?orderBy=lastMessageAt&order=desc&maxSize=3` |
| 实时更新 | WebSocket（Espo `wss://host/ws`）订阅 `ExternalConversation` 与 `OutboundTask` 变更；或 60s 轮询 |

**建议响应（dashboardStats）**：

```json
{
  "todayNewInquiries": 6, "pendingReplies": 7, "pendingReviews": 3,
  "overdueInquiries": 2, "sendFailures": 2
}
```

## 3. 客户列表（customers）

| 项 | 说明 |
| --- | --- |
| 列表 | `GET /Contact?select=name,accountId,emailAddress,phoneNumber,assignedUserId,...&offset&maxSize&orderBy=lastContactAt` |
| 搜索 | `?textFilter=关键词`（Espo 全文检索，覆盖姓名/公司/邮箱/手机号） |
| 筛选 | `where`：国家 `addressCountry`、来源 `source`、负责人 `assignedUser.name`、等级 `level`（自定义字段） |
| 响应字段 | `id, name, accountName, country, emailAddress, phoneNumber, source, level, assignedUserName, tags[], interestedProducts[], lastContactAt, createdAt` |
| 刷新 | `GET /Contact` 重新拉取；增量可用 `updatedAt > lastSync` |

> 客户实体建议以 Contact（联系人）为主、Account（公司）关联：`Contact.accountId → Account`。

## 4. 新增客户（add_customer）

| 项 | 说明 |
| --- | --- |
| 创建 | `POST /Contact` |
| 请求体 | `{"name":"客户姓名","accountId":"...","accountIdName":"公司名","addressCountry":"美国","source":"Alibaba","emailAddress":"...","phoneNumber":"...","phoneWhatsApp":"...","jobTitle":"...","level":"A","assignedUserId":"...","tags":["..."],"interestedProducts":["..."],"description":"备注"}` |
| 响应 | `{"id":"...","name":"..."}` |
| 疑似重复 | 前端先调 `GET /Contact?action=duplicateCheck` 或后端 action `POST /Contact/action/checkDuplicate`（请求：`name/accountName/emailAddress/phoneNumber`，响应：`duplicateIds[]`）；客户端展示提示后可继续提交 |
| 防重复提交 | 客户端已做（saving 状态锁）；后端建议幂等键 `Idempotency-Key` |

字段映射：`CustomerSource.ALIBABA → "Alibaba"`、`MADE_IN_CHINA → "MadeInChina"`、`INDEPENDENT_SITE → "Website"`、`EXHIBITION → "Exhibition"`、`MANUAL → "Manual"`。

## 5. 客户详情 + 历史时间线（customer_detail）

| 项 | 说明 |
| --- | --- |
| 客户概要 | `GET /Contact/{id}?select=...`（含 account 关联名） |
| 跟进概览 | 询盘数/待回复数：`GET /Contact/{id}/externalConversations?maxSize=0`（取 `total` 与 status 分布）；最近回复时间：`GET /ExternalMessage?where=[{"type":"equals","attribute":"createdById","value":"me"},{"type":"linkedWith","attribute":"conversation","value":["conversationId..."]}]&orderBy=createdAt&order=desc&maxSize=1` |
| 历史时间线 | 推荐 `GET /Contact/{id}/activityTimeline?type=all&offset&maxSize`（Espo 内置 timeline action 聚合多实体）；或按实体分别拉取：`ExternalConversation`(客户询盘)、`ExternalMessage`(回复)、`AIReplyDraft`(AI 草稿)、`Call`、`Email`、`Note`(跟进备注/资料修改) |
| 时间线条目字段 | `id, entityType, type, name(标题), body(摘要), createdByName, channel, status, createdAt, aiAssisted, conversationId` |
| 点击询盘记录 | `conversationId` → 跳转 `/chat/{conversationId}` |
| 实时更新 | 订阅 `Contact` 与关联实体 stream；简单方案：详情页可见时轮询 timeline `maxSize=20` |

## 6. 询盘列表（conversations）

| 项 | 说明 |
| --- | --- |
| 列表 | `GET /ExternalConversation?select=id,name,accountIdName,status,unreadCount,language,product,lastMessageAt,lastMessagePreview,waitingMinutes,slaBreached&orderBy=lastMessageAt&order=desc` |
| 状态筛选 | `?where=[{"type":"equals","attribute":"status","value":"Waiting"}]`（Waiting/ToReview/Replied/Closed ↔ WAITING_REPLY/WAITING_REVIEW/REPLIED/CLOSED） |
| 响应字段 | `id, customerId, customerName, companyName, country, channel, subject, status, unreadCount, language, product, lastMessageAt, lastMessagePreview, waitingMinutes, slaBreached, onlineStatus` |
| 实时更新 | WebSocket 订阅；未读徽标 = 客户端对 `unreadCount` 求和；下拉刷新调同一接口 |

## 7. 会话详情（chat）

| 项 | 说明 |
| --- | --- |
| 会话信息 | `GET /ExternalConversation/{id}` |
| 消息列表 | `GET /ExternalConversation/{id}/externalMessages?offset&maxSize=50&orderBy=createdAt&order=asc` |
| 消息字段 | `id, fromName, direction(in/out), body(原文), bodyZh(中文翻译，后端缓存), language, createdAt, status(sending/sent/failed), attachments[{name,size}], aiAssisted` |
| 发送 | `POST /ExternalMessage`：`{"conversationId":"...","body":"客户语言文本","bodyZh":"中文原文","attachmentIds":[]}`；响应含 `status`；**客户端提示"演示模式"删除**，真实发送由后端 OutboundTask 分发到阿里/WhatsApp/邮件 |
| 重试失败消息 | `POST /ExternalMessage/{id}/retry` |
| 标记已读 | `PUT /ExternalConversation/{id}`：`{"unreadCount":0}` 或 action `POST /ExternalConversation/{id}/markRead` |
| 草稿 | 本地 Room `chat_drafts` 表（客户端持有，不上传） |
| 实时更新 | WebSocket 订阅 `ExternalMessage` stream → 追加消息、更新 `deliveryStatus`、未读数；断线时显示离线条并降级轮询（10s） |
| 附件 | 上传 `POST /Attachment`（multipart，`relatedType=ExternalMessage`），消息体引用 `attachmentIds` |

## 8. AI 回复建议（chat 内弹层）

| 项 | 说明 |
| --- | --- |
| 生成 | `POST /AIReplyDraft/action/generateReply`：`{"conversationId":"...","instruction":null}` |
| 响应 | `{"id":"...","draftBody":"客户语言草稿","draftBodyZh":"中文译文","suggestedLanguage":"en","intent":"报价确认","summaryZh":"...","riskLevel":"High","confidence":0.72,"missingInformation":[],"citedKnowledge":[{"id":"...","title":"IQF 蓝莓规格书 v3.2"}],"needsManualConfirm":true,"confirmReasons":["包含价格条款"]}` |
| 重新生成 | 同上接口，重复调用即重新生成（客户端显示"AI 正在生成回复…"） |
| 采用 | `POST /AIReplyDraft/{id}`：`{"status":"Accepted"}`（不自动发送，仅回填输入框） |
| 忽略 | `POST /AIReplyDraft/{id}`：`{"status":"Dismissed"}` |
| 风险规则 | 后端根据草稿内容关键词（价格/MOQ/交期/认证/付款/折扣/质量承诺/赔偿）计算 `confirmReasons`；客户端只负责展示红色"需要人工确认"横幅 |
| 实时更新 | 生成耗时任务：WebSocket 推送 `AIReplyDraft` 创建事件，或 SSE/轮询 draft 状态（GENERATING→READY/FAILED） |

## 9. 翻译（chat 内弹层）

| 项 | 说明 |
| --- | --- |
| 检测语言 | `POST /Translation/action/detect`：`{"text":"..."}` → `{"language":"en","confidence":0.95}` |
| 翻译客户消息 | `POST /Translation/action/translate`：`{"text":"...","target":"zh"}` → `{"translated":"..."}`（后端缓存到 `ExternalMessage.bodyZh`） |
| 翻译业务员草稿 | `POST /Translation/action/translate`：`{"text":"中文","target":"es"}` |
| 展示要求 | 固定显示"机器翻译，请人工确认"；失败保留原文并提供重试（客户端已实现） |
| 实时更新 | 无需，请求-响应式；建议后端对同一文本做哈希缓存 |

## 10. 通知与异常（notifications）

| 项 | 说明 |
| --- | --- |
| 列表 | `GET /Notification?orderBy=createdAt&order=desc&maxSize=50`（Espo 内置 Notification）+ `GET /OutboundTask?where=[status=Failed]` 聚合发送异常 |
| 字段 | `id, type(SendFailure/SlaTimeout/ReviewReminder/System), title, content, level(error/warning/info), relatedType, relatedId(conversationId/customerId), read, createdAt` |
| 已读 | `PUT /Notification/{id}`：`{"read":true}`；全部已读 `POST /Notification/action/markAllRead` |
| 实时更新 | WebSocket 订阅 `Notification`；新异常时客户端发 Snackbar/顶部提示 |

## 11. 我的 / 设置（profile / settings）

| 项 | 说明 |
| --- | --- |
| 用户信息 | `GET /App/user` → `name, role, department(teams), company, emailAddress` |
| 我的统计 | `GET /Contact?where=[assignedUser=me, createdAt>=月初]`（total）+ `GET /ExternalConversation?where=[status in Waiting...]`（total） |
| 知识资料 | `GET /KnowledgeDocument?select=name,category` |
| 设置 | 主题/演示开关仅本地存储（DataStore）；不涉及后端 |
| 退出登录 | 清除本地凭证即可；如服务端有会话注销 `POST /App/action/logout` |

---

## 实时更新总结

| 方案 | 建议 |
| --- | --- |
| 首选 | EspoCRM WebSocket（`wss://.../ws`，自带心跳与 topic 订阅） |
| 订阅主题 | `ExternalConversation`、`ExternalMessage`、`AIReplyDraft`、`Notification`、`OutboundTask` |
| 降级 | 会话/询盘页可见时 10s 轮询；列表页 60s 轮询 |
| 客户端已预留 | 所有列表/会话数据均为 `Flow`（StateFlow），接入 WebSocket 后只需让真实 Repository 向同一 Flow 推送新数据，UI 无需修改 |

## 接入检查清单

- [ ] DTO ↔ 领域模型 Mapper（`data/remote/mapper/`）
- [ ] 真实 Repository 实现并替换 `di/DataModule` 绑定
- [ ] 凭证安全存储（EncryptedSharedPreferences），拦截器统一注入
- [ ] 网络错误 → UiState.Error 映射与重试（UI 已支持）
- [ ] WebSocket 客户端（如 OkHttp WebSocket / OkSse）
- [ ] 分页游标与本地 Room 缓存同步策略
- [ ] 删除演示开关（设置页"演示控制"卡片）或改为 QA 专用
