---

description: "福三和 CRM 全系统基线与生产化缺口任务"
---

# Tasks: 福三和 CRM 全系统基线

**Input**: Design documents from `/specs/001-system-baseline/`

**Organization**: 只列当前代码尚未充分满足的工作。已验证的现有能力作为基线证据，不伪造成已完成任务。

## Phase 1: Setup (Spec-Driven Baseline)

**Purpose**: 让所有后续开发和审查使用同一入口。

- [x] T001 在 `README.md` 增加 Spec Kit 工作流、当前特性和新建规格命令说明
- [x] T002 [P] 在 `docs/PROJECT_STATUS.md` 链接 `specs/001-system-baseline/spec.md` 并区分“已验证基线”与“未完成目标”
- [x] T003 [P] 在 `Makefile` 增加不读取或打印密钥的 `spec-check` 和 `verify-offline` 入口

---

## Phase 2: Foundational (P0 Security and Contract Gates)

**Purpose**: 生产接入、真实渠道和移动端前必须完成的共享安全与契约基础。

**CRITICAL**: T004–T011 未完成前，不得宣称系统已具备生产外发或 Android 生产接入能力。

- [ ] T004 为 `custom/Espo/Custom/Tools/Fusanhe/Api/AbstractFusanheAction.php` 增加统一请求 ID、成功包装和稳定错误代码映射
- [ ] T005 [P] 在 `tests/test_api_contract.py` 先添加请求 ID、错误包装、400/401/403/404/409/422/429 契约测试
- [ ] T006 对 `custom/Espo/Custom/Tools/Fusanhe/Api/` 全部业务 Action 实施实体级和记录级 ACL，覆盖 intake、草稿、知识扫描与统计接口
- [ ] T007 [P] 在 `tests/test_security_regression.py` 先添加每个变更 Action 的未授权角色拒绝测试
- [ ] T008 在 `custom/Espo/Custom/Resources/metadata/entityDefs/AutomationAgent.json` 定义单 Agent 凭证哈希、版本、到期、撤销和最后使用字段
- [ ] T009 在 `custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php` 实现单 Agent 凭证签发、常量时间哈希校验、轮换和撤销，并绑定 `agentKey`
- [ ] T010 [P] 在 `tests/test_agent_credentials.py` 先添加单 Agent 隔离、伪造 `agentKey`、过期、轮换、撤销和审计脱敏测试
- [ ] T011 在 `.env.example`、`scripts/mock-agent.py` 和 `docs/API_AGENT_HANDOFF.md` 完成共享 Token 到单 Agent 凭证的兼容迁移与回退说明

**Checkpoint**: 所有后续用户故事共用统一错误、ACL、请求追踪和 Agent 身份基础。

---

## Phase 3: User Story 1 - 统一询盘与人工审批回复 (Priority: P1)

**Goal**: 保证询盘去重、草稿快照、人工批准和停发门禁在并发与重试下仍可靠。

**Independent Test**: 重放同一询盘与批准 100 次，仅产生一条业务消息和一个发送任务；停发下领取与发送均失败。

- [ ] T012 [P] [US1] 在 `tests/test_concurrency_regression.py` 先添加询盘去重、并发批准、同会话活跃任务和并发领取测试
- [ ] T013 [US1] 在 `custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php` 使用数据库约束与事务满足 T012，不仅依赖应用层查询
- [ ] T014 [P] [US1] 在 `tests/test_outbound_pause.py` 先添加领取前、发送中前和开关竞态下的停发测试
- [ ] T015 [US1] 在 `custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php` 与 `custom/Espo/Custom/Tools/Fusanhe/Api/PostTaskSending.php` 实现发送前二次停发校验和审计

---

## Phase 4: User Story 2 - 客户与销售协作 (Priority: P1)

**Goal**: 保证客户身份关联、负责人与客服转销售可解释、可授权、可审计。

**Independent Test**: 对冲突身份执行候选、链接、建档、交接与越权尝试，状态不互相覆盖且操作全部可审计。

- [ ] T016 [P] [US2] 在 `tests/test_identity_acl.py` 先添加冲突线索、越权候选泄露、重复建档和链接改指测试
- [ ] T017 [US2] 在 `custom/Espo/Custom/Tools/Fusanhe/IdentityService.php` 实现标准化匹配证据、候选可见性过滤和链接变更审计
- [ ] T018 [P] [US2] 在 `tests/test_handoff_contract.py` 先添加会话状态、销售阶段、负责人和交接任务独立性测试
- [ ] T019 [US2] 在 `custom/Espo/Custom/Tools/Fusanhe/HandoffService.php` 满足 T018 并保留交接语境快照和幂等请求。

---

## Phase 5: User Story 3 - 可控的知识与 AI 辅助 (Priority: P1)

**Goal**: 未审核知识不进入 AI，文件失败隔离，Mock 与真实 Provider 明确区分。

**Independent Test**: 用已审核/未审核/损坏/过大文件和未配置 AI 环境生成草稿，不发生数据越界或模式伪装。

- [ ] T020 [P] [US3] 在 `tests/test_knowledge_isolation.py` 先添加审核隔离、路径越界、损坏/过大文件和单文件失败测试
- [ ] T021 [US3] 在 `custom/Espo/Custom/Tools/Fusanhe/KnowledgeScanner.php` 实施允许根目录、文件大小/类型限制、逐文件错误隔离和校验值记录
- [ ] T022 [P] [US3] 在 `tests/test_ai_context.py` 先添加未审核/过期知识排除、敏感字段排除、Mock 标识和 Provider 无效响应测试
- [ ] T023 [US3] 在 `custom/Espo/Custom/Tools/Fusanhe/AiProvider.php` 与 `custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php` 满足 T022 并对超时/限流实施有界重试

---

## Phase 6: User Story 4 - 食品外贸履约记录 (Priority: P2)

**Goal**: 将已有食品外贸状态机升级为可持续验证的端到端商业快照链。

**Independent Test**: 从规格、证书、样品、询价、报价到订单/多批交付，验证冻结、幂等、权限和超量交付拒绝。

- [ ] T024 [P] [US4] 在 `tests/test_food_trade_e2e.py` 先添加产品到多批交付的端到端快照与审计测试
- [ ] T025 [P] [US4] 在 `tests/test_security_regression.py` 扩展所有食品外贸受保护状态的通用 CRUD 绕过测试
- [ ] T026 [US4] 在 `custom/Espo/Custom/Tools/Fusanhe/OrderService.php` 与 `custom/Espo/Custom/Hooks/FusanheShipmentItem/ValidateQuantity.php` 对并发多批交付实施原子累计与超量拒绝

---

## Phase 7: User Story 5 - 可恢复的真实渠道执行 (Priority: P2)

**Goal**: 实现真实增量同步、幂等发送、限流、死信、对账与人工风控恢复。

**Independent Test**: 在隔离沙箱重放增量、重复消息、限流、超时、远端成功/本地超时、凭证撤销和风控恢复。

- [ ] T027 [P] [US5] 在 `tests/test_channel_connector_contract.py` 先为七个 Connector 方法增加游标、去重、限流、重试、对账和健康契约测试
- [ ] T028 [US5] 在 `custom/Espo/Custom/Tools/Fusanhe/Connector/AlibabaConnector.php` 实现官方消息增量同步、Webhook 签名验证与真实发送对账
- [ ] T029 [P] [US5] 在 `custom/Espo/Custom/Tools/Fusanhe/Connector/WebsiteConnector.php` 实现独立站增量同步与签名契约
- [ ] T030 [P] [US5] 在 `custom/Espo/Custom/Tools/Fusanhe/Connector/EmailConnector.php` 实现邮件增量游标、Message-ID 去重和发送结果对账
- [ ] T031 [P] [US5] 在 `custom/Espo/Custom/Tools/Fusanhe/Connector/MadeInChinaConnector.php` 实现官方能力优先的同步与发送契约
- [ ] T032 [US5] 在 `custom/Espo/Custom/Resources/metadata/entityDefs/ExternalChannel.json` 和 `custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php` 增加游标、限流、死信和对账状态持久化

---

## Phase 8: User Story 6 - 安全的移动协作 (Priority: P2)

**Goal**: 把 Android 从 Mock UI 升级为使用个人身份、真实契约、离线缓存和可恢复同步的生产客户端。

**Independent Test**: 非管理员用户在在线、弱网和离线下完成登录、客户/会话阅读、建档、草稿协作、凭证失效和恢复同步。

- [ ] T033 [P] [US6] 在 `android-client/app/src/test/java/com/fusanhe/crm/data/remote/ContractParsingTest.kt` 先添加成功/错误包装、未知枚举、分页游标和兼容性测试
- [ ] T034 [US6] 在 `android-client/app/src/main/java/com/fusanhe/crm/data/remote/dto/Dtos.kt` 与新建 `data/remote/mapper/Mappers.kt` 实现服务契约与容错映射
- [ ] T035 [P] [US6] 在 `android-client/app/src/test/java/com/fusanhe/crm/data/auth/SessionStoreTest.kt` 先添加安全会话存储、过期、注销和管理员密码不落盘测试
- [ ] T036 [US6] 在 `android-client/app/src/main/java/com/fusanhe/crm/data/auth/SessionStore.kt` 实现个人会话安全存储与撤销清理
- [ ] T037 [US6] 在 `android-client/app/src/main/java/com/fusanhe/crm/data/repository/` 实现客户、会话、翻译和 AI 草稿 Remote Repository，并在 `di/DataModule.kt` 显式切换 Mock/真实模式
- [ ] T038 [P] [US6] 在 `android-client/app/src/test/java/com/fusanhe/crm/data/sync/SyncCoordinatorTest.kt` 先添加离线、幂等重试、权限缩小、分页续传和 WebSocket 失效信号测试
- [ ] T039 [US6] 在 `android-client/app/src/main/java/com/fusanhe/crm/data/sync/SyncCoordinator.kt` 与 `data/local/` 实现 Room 缓存、待重试操作、冲突解决和断线恢复

---

## Phase 9: User Story 7 - 可审计运维与恢复 (Priority: P3)

**Goal**: 建立可重复的 CI、监控、备份恢复演练、密钥轮换和发布回退证据。

**Independent Test**: 从空白隔离环境启动、验证、备份、恢复、轮换测试凭证并注入故障，所有步骤有可检索证据。

- [ ] T040 [P] [US7] 在 `.github/workflows/verify.yml` 建立不需生产密钥的 Compose 配置、离线契约、PHP lint 和 Android 测试/lint/构建门禁
- [ ] T041 [P] [US7] 在 `tests/test_secret_regression.py` 先添加代码、规格、日志夹具和审计载荷的凭证/私密数据泄露回归测试
- [ ] T042 [US7] 在 `scripts/backup.sh`、`scripts/restore.sh` 和 `tests/test_backup_restore.py` 增加备份完整性 manifest、不完整产物拒绝和隔离恢复核对
- [ ] T043 [P] [US7] 在 `docs/operations.md` 定义健康、渠道游标滞后、死信、Agent 风控、AI 失败、备份失败和密钥轮换告警与操作手册
- [ ] T044 [US7] 在 `docs/RELEASE_HANDOFF_2026-09-21.md` 的后继发布模板中要求记录规格链接、验证证据、已知风险、数据迁移和回退结果

---

## Phase 10: Polish and Cross-Cutting Verification

- [ ] T045 [P] 在 `tests/test_spec_traceability.py` 校验新特性包含 `spec.md`、`plan.md`、`tasks.md`、需求 ID 与至少一个验证入口
- [ ] T046 按 `specs/001-system-baseline/quickstart.md` 执行完整验证并将通过/失败/跳过数更新到 `docs/PROJECT_STATUS.md`
- [ ] T047 运行 `$speckit-converge` 并将新发现缺口只追加到 `specs/001-system-baseline/tasks.md`

---

## Dependencies and Execution Order

- Phase 1 可立即开始。
- Phase 2 依赖 Phase 1，并阻断真实渠道和 Android 生产接入。
- US1–US4 在 Phase 2 后可按文件边界并行；每个故事必须先写失败测试再实现。
- US5 依赖 Phase 2 和 US1 的外发门禁；四个渠道适配器可分别评审。
- US6 依赖 Phase 2 的统一契约和 ACL，不依赖 US5。
- US7 可与 US4–US6 并行，但完整恢复演练应在所选发布范围完成后执行。
- Phase 10 依赖当次计划纳入的所有故事。

## Parallel Opportunities

- T002/T003、T005/T007/T010、T012/T014、T016/T018、T020/T022、T024/T025 均修改不同文件。
- T029–T031 是三个独立渠道适配器，可在 T027 契约固定后并行。
- T033/T035/T038 是三组独立的 Android 先行失败测试。
- T040/T041/T043 分别属于 CI、密钥回归和运维手册，可并行。

## Implementation Strategy

1. 先完成 Phase 1–2，把生产安全与契约作为唯一共享前置。
2. 继续保持 `FUSANHE_OUTBOUND_PAUSED=true`，优先收敛 US1–US3 回归证据。
3. US4 继续作为 Feature Flag 下的可验证模块。
4. US5 和 US6 各自拆成后续独立 Spec Kit 特性后实施，不在本基线一次性重写。
5. 每个可发布切片均执行分析、实施、快速验证和收敛，再进入下一切片。
