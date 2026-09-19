# 第一阶段实施计划（ZCode / codex/crm-ai-phase1-zcode）

创建时间：2026-09-20
基线提交：`b40f176`（main HEAD）
工作分支：`codex/crm-ai-phase1-zcode`
Worktree 绝对路径：`/Users/hanming/Desktop/fusanhe-crm-phase1-zcode`
原工作目录：`/Users/hanming/Desktop/福三和crm`（保持不动；其中的未提交架构图文件属于用户，不纳入本任务提交）

## 1. 只读核查结论（事实清单）

以下条目均已对照实际代码核实（文件与行为以代码为准，文档仅作参考）：

| # | 线索 | 核实结果 | 证据位置 |
|---|---|---|---|
| 1 | 陌生询盘自动创建 Lead | **属实** | `WorkflowService::matchOrCreateCustomer()` 末尾无条件 `create('Lead',...)`；intake 返回 `createdLead` |
| 2 | 会话状态混入发送状态 | **属实** | `ExternalConversation.status` 枚举含 `waitingApproval/readyToSend/sending/sent/failed`；`approve()` 写 `readyToSend`、`markSending()` 写 `sending`、`reportResult()` 写 `sent/failed` |
| 3 | 客户详情查看并跳转关联会话已实现 | **属实，优先复用** | `client/custom/src/views/fusanhe/customer-detail.js`（Account/Contact/Lead 三种详情均挂载，按 accountId/contactId/leadId 查会话与 Task） |
| 4 | AI 上下文缺客户负责人与已确认商务信息 | **属实** | `generateDraft()` 只传 country/language/product/message/history/knowledge，不含负责人、不含身份/客户资料 |
| 5 | 知识生成只查 approved 未查有效期 | **属实** | `generateDraft()`：`where(['approvalStatus'=>'approved'])->limit(5)`，无 `effectiveFrom/effectiveTo` 过滤、无 ACL 过滤、取"前 5 条"无相关性 |
| 6 | 已审核文件更新后未重新审核 | **属实** | `KnowledgeScanner::scan()` 更新 checksum/extractedText 时不重置 `approvalStatus`，approved 文档内容变更后仍为 approved |
| 7 | 自定义接口记录级权限不完整 | **属实** | `PostMockIntake`、`PostGenerateDraft`、`PostKnowledgeScan`、`GetDashboard`、`GetStatus` 仅登录即可；只有 `PostApproveDraft` 检查 `OutboundTask:create` |
| 8 | 全局停发只在领取时检查 | **属实** | `claim()` 检查 `FUSANHE_OUTBOUND_PAUSED`；`markSending()`、`reportResult()` 不检查，已领取任务在停发开启后仍可继续执行并写入 sent 消息 |
| 9 | Mock Agent 按真实渠道类型领取任务 | **属实** | `mock-agent.py` 注册 `capabilities:['Alibaba','MadeInChina']`；`claim()` 只按渠道类型匹配，无 mock/real 隔离标记 |
| 10 | 审计操作者固定为 `current` | **属实** | `generateDraft()` 调 `audit('draft.generated','user','current',...)` |
| 11 | 批准任务正文无不可变快照 | **属实** | `approve()` 建任务时写 `payload=['body'=>draftText]`，但 `taskPayload()` 在领取时从草稿实时读取 `draftText`，批准后改草稿会改变待发正文 |
| 12 | 身份唯一性只按渠道类型 | **属实** | `intake()` 按 `ExternalChannel.type` 找/建渠道（同类型共用一条渠道记录），会话唯一索引 `channelId+externalId`；`externalUserId` 不参与任何唯一性；无渠道账号实例概念 |
| 13 | 标准 CRUD 可绕过状态机 | **属实（推定+机制确认）** | 自定义实体 Controller 全部继承 `\Espo\Core\Controllers\Record`，PATCH `/AIReplyDraft/:id` 可把 status 直接改为 approved、PATCH `/ExternalConversation/:id` 可直接写 sent，服务层无拦截 |
| 14 | 会话/消息/任务幂等基础 | **已有** | 唯一索引：会话 `channelId+externalId`、消息 `conversationId+contentHash`、任务 `idempotencyKey`；intake/approve 幂等返回 |
| 15 | 运行环境 | Docker daemon 已启动、无任何运行容器、8080/8081 空闲；本机无 PHP、无 docker 前容器在跑 | 隔离测试可行（独立 compose 项目/端口/卷） |

## 2. 能力盘点

- **已实现**：统一询盘入库（含消息去重）、AI 草稿生成（OpenAI 兼容 + 确定性 Mock）、人工批准建幂等任务、执行端注册/心跳/领取/回写、三次重试、领取超时恢复、同会话串行发送、全局停发开关、知识扫描（PDF/DOCX/XLSX/TXT/MD）、审计、角色基线、Web 工作台（列表/详情/客户概览）、前端离线测试。
- **Mock/演示**：全部渠道为占位连接器；Mock AI；mock-agent.py 一次性执行端；Android 纯 Mock（本阶段不触碰）。
- **缺失（本阶段补齐）**：跨渠道身份映射与人工确认、客服转销售（原生 Task）、接待控制模式（AI 辅助/人工接管）、发送状态与会话状态拆分、人工草稿入口、任务正文快照、知识有效期与变更重审、接口 ACL、CRUD 状态机防绕过、Mock/真实隔离、双模块入口。

## 3. 数据归属与变更设计（全部增量兼容）

### 新实体 `ExternalIdentity`（跨渠道身份映射）
- 字段：`name`（展示名）、`identityKey`（唯一键，见下）、`channelType`、`channelAccountId`（渠道账号实例标识）、`externalUserId`、`displayName`、`emailAddress`、`phoneNumber`、`country`、`linkStatus`（`unlinked`/`confirmed`）、`account`/`contact`/`lead`（三选一 link，可空）、`confirmedBy`、`confirmedAt`、`firstSeenAt`、`lastSeenAt`、`notes`。
- 唯一索引：`identityKey`。构造规则：
  - 有 `externalUserId`：`{channelType}|{channelAccountId}|uid:{externalUserId}` —— 包含渠道账号实例，不同渠道账号的同名 externalUserId 不会合并。
  - 无 `externalUserId` 但有邮箱：`{channelType}|{channelAccountId}|email:{email}`；
  - 无前两者但有电话：`...|phone:{phone}`；
  - 全缺（匿名访客）：`{channelType}|{channelAccountId}|anon:{conversationExternalId}` —— 每个会话独立身份，绝不把匿名访客合并到一起。
- 不批量改写任何既有 Lead/Account/Contact；确认关联只由授权用户显式触发。

### `ExternalConversation` 增量字段
- `identity`（link → ExternalIdentity，可空，旧数据为 null 兼容）。
- `controlMode`（enum：`aiAssist` 默认 / `human`）——接待控制模式，与旧 `status` 分离。
- 旧 `status` 枚举**追加** `replied`（不删除旧值）；新逻辑发送成功写 `replied`，不再新写 `sending/sent/failed`（历史行保留原值可正常显示）；`needsManualMatch` 语义保留。

### `ExternalChannel` 增量字段
- `accountHandle`（varchar，可空）——渠道内账号实例（店铺/邮箱地址等）。intake 按 `type+accountHandle` 定位渠道记录；为空时按 `default` 处理，历史数据天然兼容。

### `OutboundTask` 增量字段
- `executionMode`（enum：`mock`/`real`，默认 `mock`）——Mock 任务与真实任务隔离。
- `contentSnapshot`（text）——批准时锁定的不可变回复正文；领取 payload 改从快照读取。

### `AutomationAgent` 增量字段
- `mode`（enum：`mock`/`real`，默认 `mock`）——模拟执行端只能领取 `executionMode=mock` 的任务。

### 原生 `Task` 增量字段
- `fusanheHandoffKey`（varchar 100，唯一索引，可空）——客服转销售的幂等键；空值不影响普通 Task。

### `KnowledgeDocument`
- 不加字段；扫描器在 checksum 变化时把 `approvalStatus` 重置为 `draft`（重新审核），草稿生成按 `approved + effectiveFrom/effectiveTo + 用户读取权限` 过滤。

### 防绕过 Hooks（`custom/Espo/Custom/Hooks/`）
- `AIReplyDraft`：approved/sent 后禁止再改 draftText/status（普通 PATCH），服务层用保存选项 `fusanheService=true` 豁免。
- `OutboundTask`：非豁免保存禁止改 status/claimedBy/idempotencyKey/payload。
- `ExternalConversation`：非豁免保存禁止把 status 直接写成 `sending/sent/failed/replied`、禁止直接改 `controlMode`（必须走 API 审计）。
- `ExternalMessage`：非豁免禁止创建 `direction=outbound` 消息（只能由任务回写服务创建）。

## 4. 服务拆分（WorkflowService 保留为兼容协调入口）

- `IdentityService`：identityKey 构造与 upsert、候选查询（强匹配：email/phone 精确，且逐条过 ACL read）、显式确认关联（服务端校验+审计）、显式建档（Lead/Account+Contact）。
- `HandoffService`：会话 → 原生 Task（parent 指向会话、需求摘要、负责人、截止时间、幂等键、审计、权限校验）。
- `ControlService`：人工接管/恢复辅助（服务端校验+审计）、任务取消、停发与控制模式一致性校验的共用判定。
- `WorkflowService`：保留既有公开方法签名（intake/generateDraft/approve/claim/…），内部委托并修正（intake 停止自动建 Lead、知识过滤、快照、actorId、停发一致性）；新动作通过新服务类挂到新路由。
- 不建工作流引擎/事件总线/新框架；事务、唯一约束、幂等全部用现有 EspoCRM ORM + MySQL 索引能力。

## 5. 新增/修改接口清单（均登录态 + ACL）

| 路由 | 方法 | 权限门 | 说明 |
|---|---|---|---|
| `/Fusanhe/identity/:id/candidates` | GET | `ExternalIdentity:read` + 目标实体 read 过滤 | 强匹配候选，弱证据不返回不自动确认 |
| `/Fusanhe/identity/:id/link` | POST | `ExternalIdentity:edit` + 目标 read + 会话 edit 校验 | 确认关联已有 Account/Contact/Lead，记录前后关联与操作者 |
| `/Fusanhe/identity/:id/create-customer` | POST | `ExternalIdentity:edit` + 目标实体 create | 显式建档（默认 Lead），不静默 |
| `/Fusanhe/conversation/:id/handoff` | POST | `Task:create` + 会话 read + 分配权限校验 | 幂等创建跟进 Task，返回同一业务结果 |
| `/Fusanhe/conversation/:id/control` | POST | `ExternalConversation:edit` | 人工接管/恢复辅助，审计 |
| `/Fusanhe/conversation/:id/manual-draft` | POST | `AIReplyDraft:create` | 人工草稿，走同一审核/批准/任务流 |
| `/Fusanhe/task/:id/cancel` | POST | `OutboundTask:edit`（记录级） | 取消未发送任务，审计 |
| `/Fusanhe/mock/intake` | POST | `ExternalConversation:create`（收紧） | 不再自动建 Lead |
| `/Fusanhe/conversation/:id/generate-draft` | POST | `AIReplyDraft:create` + 会话 read | 知识按有效期/ACL 过滤 |
| `/Fusanhe/knowledge/scan` | POST | `KnowledgeDocument:edit` | 变更重置审核 |
| `/Fusanhe/status`、`/Fusanhe/dashboard` | GET | 登录 + `ExternalConversation:read` | 保持只读 |

Agent 接口（noAuth + Token）保持，但 `markSending/reportResult` 增加停发与控制模式一致性校验；`claim` 按 agent.mode 过滤 executionMode。

## 6. 页面与入口（A/E）

- `#Home`（默认）改为双模块入口页：CRM 工作台 / AI 客服工作台两张卡片 + 全局停发横幅 + 关键计数。
- 新增 `#Home/crm`（`custom:views/fusanhe/crm-home`）：客户、联系人、线索、跟进任务聚合；商机保留原生导航入口。
- 新增 `#Home/service`（`custom:views/fusanhe/service-home`）：统一收件箱、待审核草稿、身份待确认、发送异常；执行端等管理入口按 `checkScope` 角色显示。
- 旧路由 `#ExternalConversation/...`、`#Account/...` 等全部保留兼容；原"外贸工作台"指标并入两个模块页，不再单页承载。
- 会话工作台（detail.js）新增：身份确认卡（候选/建档/关联）、接管/恢复按钮、人工草稿按钮、转销售表单（摘要/负责人/截止时间）、状态拆分徽章；模拟回执显式标注。
- 客户详情（customer-detail.js）新增：接待人与客户负责人并列显示、身份确认状态；会话↔客户双向跳转复用现有实现。

## 7. 小步实施顺序（每步独立提交）

1. 计划文档（本文件）。
2. 元数据：新实体/新字段/索引/枚举追加 + 语言包。
3. Hooks 防绕过 + 语言包文案。
4. IdentityService + intake 改造（不建 Lead）。
5. ControlService（接管/恢复/取消）+ claim/sending/result 一致性校验 + 快照。
6. HandoffService（转销售幂等 Task）。
7. 路由与 API Action（含既有接口 ACL 收紧、审计 actor 修复、知识过滤、scanner 重审）。
8. 前端：双入口页 + 会话工作台 + 客户详情 + 列表徽章。
9. 测试：离线契约/结构测试 + 前端 node 测试 + 隔离环境运行时测试。
10. 独立审查与修复。
11. 交接文档 PHASE1_ZCODE_HANDOFF.md。

## 8. 验收矩阵（对应任务书"七、验证要求"14 项）

| # | 验收项 | 验证方式 |
|---|---|---|
| 1 | 新访客不自动建 Lead | 运行时：intake 新访客 → `createdLead` 不存在、identity `unlinked` |
| 2 | 重复导入幂等 | 运行时：同 payload 两次 intake → 同会话同消息 `deduplicated` |
| 3 | 不同渠道账号不合并 | 运行时：同 externalUserId 不同 accountHandle → 两条 identity、两条会话 |
| 4 | 弱匹配需人工确认、越权候选不泄露 | 运行时：无强匹配时候选为空；普通用户查询候选不越权（403/过滤） |
| 5 | 确认关联后双向跳转 | 运行时：link 后会话带客户 link；客户详情会话查询命中 |
| 6 | handoff 幂等 | 运行时：同参数两次 → 同一 taskId |
| 7 | 负责人与接待人独立 | 运行时：conversation.assignedUser ≠ 客户 assignedUser 并存 |
| 8 | 无权限用户被拒 | 运行时：业务员调 link/handoff(无 Task:create)/approve/cancel → 403 |
| 9 | 接管/停发阻止未发送任务 | 运行时：controlMode=human 或 paused=true 时 claim/sending/result 被拒 |
| 10 | 已批准任务正文不受后续编辑影响 | 运行时：approve → PATCH 草稿 → claim payload 仍为快照（PATCH 被 hook 拒绝则双重验证） |
| 11 | 过期/未审/变更知识不入上下文 | 运行时：构造 expired/draft/checksum 变更文档 → 生成的草稿 citedKnowledge 不含 |
| 12 | 渠道故障不影响 CRM | 离线：intake 与 handoff 不依赖连接器；渠道 healthCheck 异常不阻断 |
| 13 | 原有 Mock 闭环仍可演示 | 运行时：intake → 草稿 → 批准 →（隔离环境临时停发关闭）claim → 回写 → 模拟回执标识 |
| 14 | 加载失败/空数据/无权限/冲突反馈 | 前端测试 + 页面错误分支保留 + API 400/403/409 语义 |

## 9. 回退方案

- 全部变更在独立分支；`git worktree` 隔离，原目录不受影响。
- 回退 = 丢弃分支（不合并即无影响）；若已在新环境部署过，删除独立 compose 项目（`fusanhe-phase1-test`）与对应卷即可，不触碰原 `fusanhe-crm` 项目。
- 元数据回退后执行 rebuild：新增列/表残留无害（EspoCRM 不因多余列报错）；未删除任何原字段或原枚举值。

## 10. 风险与保守默认（记录在案）

- EspoCRM 10.0.8 内部 API（Acl 实体级检查、Task.parent entityList、hooks 选项透传）在实现前从容器镜像源码核对，不用猜测签名；无法核实的点退化为"scope 级检查 + 显式 own 比对"的保守默认。
- `replied` 状态为追加值；`waitingApproval` 等旧值含义不变。
- 建档动作默认创建 Lead（不自动建 Account+Contact），避免制造重复客户。
- 不实现自动回复；`controlMode=aiAssist` 仍需人工批准。
- Android 不改。
