# Feature Specification: CRM 触达证据与 AI 背调

**Feature Branch**: `009-outreach-evidence-research`
**Created**: 2026-10-03
**Status**: Draft
**Input**: CRM 先行改造：为未来 Muse 的每次社交媒体触达保存截图、客户资料和 AI 背调报告。

## User Scenarios & Testing

### User Story 1 - 留存每次触达证据 (Priority: P1)

业务员或未来的 Muse 执行器可以向 CRM 提交一次已完成或待核对的触达记录，包含客户、平台、消息正文、平台消息 ID 和发送后的截图。CRM 持久化截图及校验信息，记录不会触发第二次外发。

**Why this priority**: 后续接入 Muse 前必须先建立可审计的证据闭环。

**Independent Test**: 用受控的图片 data URL 创建一条触达记录，读取记录和私有截图内容，确认重复幂等且不会创建发送任务。

**Acceptance Scenarios**:

1. **Given** 客户已存在且图片合法，**When** 提交相同幂等键两次，**Then** CRM 返回同一条记录且只保存一个截图文件。
2. **Given** 图片过大、格式错误或客户未授权读取，**When** 提交或读取，**Then** 请求被拒绝且不产生半成品证据。

### User Story 2 - AI 背调客户 (Priority: P2)

业务员可以对触达记录关联的客户发起 AI 背调。CRM 使用客户资料、公开身份线索和已有会话上下文进行联网检索，生成带来源 URL 的结构化报告，保存模型、版本、时间和失败状态。

**Why this priority**: 触达截图只回答“发了什么”，背调报告回答“客户是谁、是否值得继续跟进”。

**Independent Test**: 使用注入的文本网关夹具运行一次研究，确认报告只保留允许的来源 URL，模型失败时记录可重试的失败状态。

**Acceptance Scenarios**:

1. **Given** 触达记录包含客户身份线索，**When** 发起背调，**Then** 报告包含匹配状态、客户摘要、来源和下一步建议。

### User Story 3 - 在客户工作台查看证据 (Priority: P3)

业务员可以在 CRM 客户详情中查看触达历史、截图、发送内容、背调状态和来源，不需要进入 Muse 或外部平台。

**Why this priority**: 让 CRM 成为审计和销售决策的唯一工作台。

**Independent Test**: 使用真实权限读取一条触达记录，确认无权限用户无法读取截图和客户资料。

**Acceptance Scenarios**:

1. **Given** 记录存在截图和背调，**When** 打开客户详情，**Then** 页面显示缩略图、消息和带来源的背调摘要。

## Edge Cases

- 截图上传成功但背调失败：保留截图和发送事实，背调标记 `failed`，可重试，不重复触达。
- 发送结果不确定：状态为 `uncertain`，不自动重发，等待人工核对。
- 同一平台消息 ID 重复回传：内容一致则幂等，内容冲突则拒绝。
- 客户已退订、受限或没有合法联系策略：只允许留档，不允许把记录标记为可继续触达。
- 图片包含无关会话或敏感信息：限制 MIME、大小和尺寸，并保留私有存储访问控制。

## Requirements

### Functional Requirements

- **FR-001**: CRM MUST persist one `OutreachEvidence` record per idempotent outreach attempt and link it to a Lead, Account, Contact or ExternalConversation.
- **FR-002**: CRM MUST accept only bounded PNG, JPEG or WebP screenshots and store bytes privately with SHA-256 and MIME/size metadata.
- **FR-003**: CRM MUST record platform, public profile URL, external message ID, message body, send status, sent time and customer snapshot.
- **FR-004**: Replaying the same idempotency key or external message ID with identical content MUST return the existing record; conflicting content MUST be rejected.
- **FR-005**: Screenshot retrieval MUST require CRM entity-level read permission and MUST never expose a public storage URL.
- **FR-006**: CRM MUST provide a research action that uses the configured text gateway web-search flow and stores structured results, source URLs, model, prompt version and timestamps.
- **FR-007**: AI research MUST treat customer and web text as untrusted evidence, must not send messages, and must not infer sensitive attributes.
- **FR-008**: Research failures MUST preserve the outreach evidence and expose a bounded retryable status without creating an outbound task.
- **FR-009**: All evidence and research mutations MUST create an audit event with actor, request ID, entity ID and safe identifiers.
- **FR-010**: This feature MUST not connect to Muse, browse social platforms, or send external messages in this phase.

### Key Entities

- **OutreachEvidence**: One completed or uncertain external contact attempt, including private screenshot, message facts, target links and research state.
- **ProspectResearch**: The latest structured AI research snapshot for a target, with evidence URLs, match status, confidence, model and prompt version.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of accepted evidence records expose message facts, a bounded screenshot reference and an auditable actor/request ID.
- **SC-002**: Replaying an evidence submission never creates a duplicate record or duplicate stored screenshot.
- **SC-003**: A completed research report contains only URLs returned by the configured search provider and a visible model/prompt version.
- **SC-004**: The feature can be demonstrated end to end in CRM with no Muse account and no external message sent.

## Assumptions

- CRM authentication and ACL are reused.
- The first phase receives screenshots as bounded data URLs; a Muse upload adapter will be added later.
- AI research uses the existing `TextGateway::research` web-search contract and existing privacy policy as its base.
- Social-platform discovery, external sending, daily sending quota and Muse orchestration are out of scope here.
