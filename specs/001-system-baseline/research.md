# Research: 福三和 CRM 全系统基线

## Decision 1: 单一根级 Spec Kit 项目

**Decision**: Web CRM、自定义 API、Android 和执行端共用一份宪章与 `specs/` 编号空间。

**Rationale**: 它们共享客户身份、会话、权限、状态机和外发门禁，单一边界能保持契约所有权。

**Alternatives considered**: 为 Android 和 CRM 分别初始化；这会使共享 API 契约与端到端验收分裂。

## Decision 2: 基线是活契约，新变更是独立特性

**Decision**: `001-system-baseline` 记录稳定边界与已知缺口；实施项必须拆为 `002-*` 及后续规格。

**Rationale**: 全系统一次性重写不可审查；仅记下一个小功能又无法实现“整个项目”的统一性。

**Alternatives considered**: 倒推数十个历史规格；这会制造伪精确历史。

## Decision 3: EspoCRM 继续作为系统记录

**Decision**: 保留 EspoCRM 10.0.8 + MariaDB 11.4，自定义限定在 `custom/` 与 `client/custom/`，不修改 core/vendor。

**Rationale**: 当前实体、权限、状态机、页面和运行时测试均基于此平台且已能完成 Mock 闭环。

**Alternatives considered**: 立即拆出独立后端；当前收益不足以支撑迁移与数据风险。

## Decision 4: 状态与权限以服务端为权威

**Decision**: Web、Android 和执行端均通过服务端契约、ACL、写入守卫和业务状态机。

**Rationale**: 客户数据、外发、报价和订单是高影响操作，前端按钮或 Feature Flag 可被绕过。

**Alternatives considered**: 客户端预校验后直写通用实体；预校验可保留，但不能替代服务端校验。

## Decision 5: 执行端使用单 Agent 凭证

**Decision**: 将共享 `FUSANHE_AUTOMATION_TOKEN` 迁移为每 Agent 独立凭证，只存哈希，支持轮换与撤销。

**Rationale**: 共享 Token 无法定位泄露、单独撤销或可靠归因。

**Alternatives considered**: 共享 Token + `agentKey`；`agentKey` 可伪造，不是身份证明。

## Decision 6: 真实渠道官方契约优先，不确定发送先对账

**Decision**: 优先官方 API/Webhook，各渠道独立管理游标、限流、幂等键、重试、死信和发送对账。

**Rationale**: 远端成功后本地超时的情形下，盲目重试会向客户重复发送。

**Alternatives considered**: 所有渠道统一固定次数重试；它忽略渠道特定签名、限流与风控语义。

## Decision 7: Android 保留分层，逐步替换 Mock Repository

**Decision**: 保留 domain repository 接口、ViewModel 和 Compose UI，增加安全认证、DTO Mapper、Remote Repository、
Room 缓存和同步协调；Mock 演示作为显式模式保留。

**Rationale**: 界面与抽象已存在，替换数据层比重写 UI 风险低，也保留演示基线。

**Alternatives considered**: 删除 Mock 一次性重写；这会扩大回归范围并丢失可演示能力。
