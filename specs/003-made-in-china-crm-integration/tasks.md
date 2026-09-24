# Made-in-China CRM 接入任务

所有任务未开始。详细文件、契约、步骤及测试命令见 [实施计划](../../docs/superpowers/plans/2026-09-23-made-in-china-crm-integration.md)。

- [ ] T001 [MIC-01] 只读发现完整 TradeMessenger 双向历史，建立脱敏夹具和源契约证据。
- [ ] T002 [MIC-01, MIC-02] 补齐网关的列表分页、历史消息解析、稳定源 ID、顺序与买家资料。
- [ ] T003 [MIC-02, MIC-03] 定义并实现 CRM MIC 入库 API、身份/Lead 关联及无副作用回填。
- [ ] T004 [MIC-02] 实现 MIC→CRM 桥接 CLI 的注册、回填、单轮、守护、状态和重试。
- [ ] T005 [MIC-04] 实现 MIC 出向 Agent 的领取、停发校验、网关 Outbox 提交及状态对账。
- [ ] T006 [MIC-01, MIC-03, MIC-04, MIC-05] 执行离线、隔离 CRM、只读现场及指定会话发送验收，更新运维与状态文档。
