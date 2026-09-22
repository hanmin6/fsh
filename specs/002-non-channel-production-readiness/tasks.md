# Tasks: 非渠道生产化收敛

## Phase 1: API and Agent Security

- [x] T001 [P] [US1] 在 `tests/test_api_contract.py` 添加 ACL、请求 ID 与稳定错误契约测试
- [x] T002 [US1] 在 `custom/Espo/Custom/Tools/Fusanhe/Api/AbstractFusanheAction.php` 增加请求 ID 和安全错误帮助器
- [x] T003 [P] [US2] 在 `tests/test_agent_credentials.py` 添加绑定、轮换、撤销、过期和脱敏测试
- [x] T004 [US2] 在 `custom/Espo/Custom/Resources/metadata/entityDefs/AutomationAgent.json` 增加哈希凭证生命周期字段
- [x] T005 [US2] 在 `custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php` 实现单 Agent 凭证签发与校验
- [x] T006 [US2] 在 `custom/Espo/Custom/Tools/Fusanhe/Api/PostAgentRegister.php` 实现兼容注册与一次性凭证返回
- [x] T007 [US2] 在 `custom/Espo/Custom/Tools/Fusanhe/Api/PostAgentHeartbeat.php` 和 Agent 任务 Action 中绑定凭证与 `agentKey`

## Phase 2: Internal Safety

- [x] T008 [P] [US1] 在 `tests/test_knowledge_scanner_contract.py` 添加路径、类型、大小与单文件隔离测试
- [x] T009 [US1] 在 `custom/Espo/Custom/Tools/Fusanhe/KnowledgeScanner.php` 实现扫描根边界和文件限制
- [x] T010 [P] [US1] 在 `tests/test_phase1.py` 扩展并发/幂等/发送前二次停发的静态契约测试

## Phase 3: Android Production Data Foundation

- [x] T011 [P] [US3] 在 `android-client/app/src/test/java/com/fusanhe/crm/data/remote/DtoMapperTest.kt` 添加 DTO 容错与领域映射测试
- [x] T012 [US3] 在 `android-client/app/src/main/java/com/fusanhe/crm/data/remote/mapper/Mappers.kt` 实现客户、会话、消息与草稿映射
- [x] T013 [P] [US3] 在 `android-client/app/src/test/java/com/fusanhe/crm/data/auth/SessionStoreTest.kt` 添加会话存储和退出清理测试
- [x] T014 [US3] 在 `android-client/app/src/main/java/com/fusanhe/crm/data/auth/SecureSessionStore.kt` 实现不落盘密码的加密会话存储
- [x] T015 [US3] 在 `android-client/app/src/main/java/com/fusanhe/crm/data/repository/RemoteRepositories.kt` 实现真实客户、会话和草稿 Repository
- [x] T016 [US3] 在 `android-client/app/src/main/java/com/fusanhe/crm/di/DataModule.kt` 和 `AppModule.kt` 实现 BuildConfig 显式 Mock/真实模式、基址与会话头注入

## Phase 4: CI and Recovery

- [x] T017 [P] [US4] 在 `.github/workflows/verify.yml` 实现 Spec、Python、PHP 和 Android 门禁
- [x] T018 [US4] 在 `scripts/backup.sh` 产生 SHA-256 manifest，并在 `scripts/restore.sh` 覆盖前强制验证
- [x] T019 [P] [US4] 在 `docs/operations.md` 增加健康、脱敏、凭证轮换、恢复和回退手册
- [x] T020 [US4] 执行 `specs/002-non-channel-production-readiness/quickstart.md` 并记录所有跳过与外部阻塞

## Phase 5: Convergence

- [x] T021 让 `custom/Espo/Custom/Tools/Fusanhe/Api/FusanheApiMiddleware.php` 的成功/错误响应和审计使用同一请求 ID，依据 FR-002 / US1-AC2 (partial)
- [x] T022 在 `android-client/app/src/main/java/com/fusanhe/crm/data/repository/RemoteRepositories.kt` 于退出或 401 后清除受限缓存，依据 FR-010 / FR-011 (partial)
- [x] T023 扩展 `tests/test_phase1_runtime.py` 的隔离 CRM ACL 运行时回归并覆盖自定义 Action 边界，依据 SC-001 (partial)
- [x] T024 在 `tests/test_phase1_runtime.py` 添加双 Agent 绑定、轮换、撤销与互不影响的运行时测试，依据 SC-002 (partial)
- [x] T025 将 `android-client/app/src/test/java/com/fusanhe/crm/data/remote/CrmApiServiceTest.kt` HTTP 容错和备份篡改拒绝纳入门禁，依据 US3 Independent Test / SC-004 (partial)
