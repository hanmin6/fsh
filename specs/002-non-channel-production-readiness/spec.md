# Feature Specification: 非渠道生产化收敛

**Feature Branch**: `main`
**Created**: 2026-09-21
**Status**: Approved
**Input**: User description: "除了渠道接入以外，其他可开发项一次性用 AI 完成"

## Scope

本特性一次收敛 CRM 内部生产化能力：API 授权与错误契约、单 Agent 凭证、并发/幂等安全、
知识隔离、Android 真实数据基础、CI、备份恢复与运维文档。

**Out of scope**: Alibaba、Made-in-China、独立站、邮件等真实渠道的消息同步与对外发送。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 安全可追踪的 CRM API (Priority: P1)

业务用户和管理员只能访问其角色与记录范围内的业务操作，每次请求有稳定错误与请求 ID。

**Independent Test**: 用管理员、授权业务员和受限用户执行全部自定义 Action，权限与错误包装结果均可预期。

**Acceptance Scenarios**:

1. **Given** 用户无记录级编辑权，**When** 调用变更 Action，**Then** 请求被拒绝且不产生副作用。
2. **Given** 请求携带或未携带请求 ID，**When** 返回成功或错误，**Then** 响应和审计可用同一 ID 关联。

### User Story 2 - 独立可撤销的 Agent 身份 (Priority: P1)

管理员能为每个执行端签发仅显示一次的凭证，并单独轮换或撤销，不影响其他 Agent。

**Independent Test**: 两个 Agent 分别认证，撤销一个后只有该 Agent 被拒绝，数据库与日志不出现明文凭证。

**Acceptance Scenarios**:

1. **Given** Agent 凭证有效，**When** 请求声明另一 `agentKey`，**Then** 请求被拒绝。
2. **Given** Agent 凭证已撤销，**When** 心跳、领取或回写，**Then** 请求被拒绝并保留脱敏审计。

### User Story 3 - Android 真实数据就绪 (Priority: P2)

移动用户能使用个人凭证访问 CRM，客户端安全保存会话、映射客户/会话/草稿契约，并可在 Mock 与真实模式间显式选择。

**Independent Test**: 用 MockWebServer 验证登录、列表、详情、建档、草稿、错误、未知枚举、退出和断线缓存。

**Acceptance Scenarios**:

1. **Given** 选择真实模式，**When** 登录成功，**Then** 仅安全保存个人会话凭证，不保存密码。
2. **Given** 后端返回新枚举或额外字段，**When** 客户端解析，**Then** 不崩溃且显示安全降级状态。

### User Story 4 - 可验证的发布与恢复 (Priority: P2)

开发与运维人员能通过统一命令验证规格、契约、PHP、Android 与 Compose，并使用带完整性清单的备份做隔离恢复。

**Independent Test**: CI 在无生产密钥时通过静态/离线门禁；篡改备份后恢复被拒绝，完整备份可在隔离环境恢复。

**Acceptance Scenarios**:

1. **Given** 备份文件不完整或校验不匹配，**When** 请求恢复，**Then** 在覆盖目标数据前失败。
2. **Given** 代码将密钥或未脱敏载荷写入可追踪文件，**When** CI 运行，**Then** 门禁失败。

### Edge Cases

- 兼容期旧 Agent 共享 Token 仅能用于注册/换取独立凭证，不能长期执行任务。
- 并发批准、领取和交付量更新只产生一次有效业务结果。
- Android 会话失效或权限缩小后，受限缓存不继续对用户可见。
- 知识文件越出允许根目录、过大、损坏或格式不允许时单文件隔离。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 所有自定义业务 Action MUST 在服务端实施 scope 与 record ACL。
- **FR-002**: 自定义 Action MUST 使用稳定错误代码和请求 ID，且不在错误中暴露敏感值。
- **FR-003**: GET 与健康类接口 MUST 无业务副作用。
- **FR-004**: 每 Agent MUST 使用独立、哈希存储、可轮换、可撤销的凭证。
- **FR-005**: Agent 凭证 MUST 与 `agentKey` 绑定，且明文只在签发时显示一次。
- **FR-006**: 共享旧 Token MUST 有明确兼容截止日期与失败关闭迁移方法。
- **FR-007**: 询盘、批准、任务领取和食品外贸快照 MUST 在并发重试下保持幂等。
- **FR-008**: 知识扫描 MUST 实施根目录、类型、大小、校验值和逐文件失败隔离。
- **FR-009**: Android MUST 提供真实 API DTO/Mapper/Repository 和明确 Mock/真实模式。
- **FR-010**: Android MUST 安全保存会话凭证，不得保存密码，退出时清理受限数据。
- **FR-011**: Android MUST 对未知枚举、额外字段、断线和会话失效安全降级。
- **FR-012**: CI MUST 执行 Spec Kit 检查、离线契约、PHP lint 和 Android 测试/lint/构建。
- **FR-013**: 备份 MUST 包含带校验值的 manifest，恢复 MUST 在覆盖前验证完整性。
- **FR-014**: 仓库 MUST 提供脱敏、健康、恢复、密钥轮换和发布回退手册。
- **FR-015**: 全局停发 MUST 保持默认开启，本特性 MUST NOT 执行真实渠道发送。

## Success Criteria *(mandatory)*

- **SC-001**: 自定义 Action 权限回归覆盖率 100%，未授权请求不产生副作用。
- **SC-002**: 撤销单 Agent 凭证后，其他 Agent 继续可用，明文凭证搜索结果为 0。
- **SC-003**: Android 单元测试不再是 `NO-SOURCE`，契约、会话和 Mapper 测试通过。
- **SC-004**: 篡改任一备份文件后，恢复在覆盖目标数据前失败。
- **SC-005**: `make spec-check` 和 `make verify-offline` 通过，CI 定义可在无生产密钥环境解析。

## Assumptions

- 真实渠道凭证、Webhook 和发送不在本次范围。
- Android 真实模式先提供可构建、可测试的数据与会话基础；生产服务器地址与用户凭证由部署环境提供。
- 不更改 EspoCRM core/vendor，不提交任何真实密钥。
