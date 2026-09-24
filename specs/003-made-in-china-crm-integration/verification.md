# Made-in-China CRM 接入验证记录

更新时间：2026-09-24。当前记录包含全量离线、契约、运行时测试，以及真实数据库与现场 CRM 导入核对证据。

## 1. 自动化测试套件

- **MIC 网关与桥接自动化测试（`made-in-china`）**：
  - 测试命令：`pytest`
  - 结果：**274 passed, 3 skipped**。
  - 覆盖范围：包含 TradeMessenger DOM 提取契约、历史消息解析、图片附件降级提取、CRM Bridge 导入器、出向 Worker 调度、安全凭证与审计等。
- **CRM 契约与运行时测试套件（`fsh`）**：
  - 契约测试：`pytest tests/test_mic_sync_contract.py` → **18 passed**。
  - 运行时测试：`RUN_MIC_SYNC_RUNTIME=1 pytest tests/test_mic_sync_runtime.py` → **9 passed**。
  - 总计：**27 passed, 0 failed**。
  - 覆盖范围：MIC 买家身份到 Lead 的解析与复用、独立买家隔离、国家与姓名更新、消息幂等去重、附件元数据透传、并发导入锁等。

## 2. 现场数据与实体核对证据

- **Gateway 数据库（`G:\MadeInChinaGatewayData\gateway.db`）**：
  - 数据库迁移版本：`0002_message_history`。
  - 会话同步状态：**10 / 10** 会话全部完成历史同步，`history_complete = 1`。
  - 消息总量：**94 条** 完整双向历史消息（包含 10 条 initialInquiry 初始询盘、30 条 inbound 聊天、54 条 outbound 聊天，以及图片附件元数据）。
  - 买家信息提取：正确提取 10 个独立买家 customer ID（从 `#customer-detail/<id>` 获取，已彻底根除销售代表 ID `EEnxEJQbMJmm` 混淆问题）、姓名及国家。
- **现场 CRM（`http://127.0.0.1:18080/api/v1`）回填验证**：
  - 执行 `crm_bridge_pipeline.py` 进行 `importer.backfill()`：
    - `conversations`: 10
    - `messages`: 94
    - `batches`: 10
    - `action_required_codes`: []
  - MariaDB 实体核对：
    - `lead`: 生成 10 个独立 Lead 记录，姓名均已升级为真实买家姓名，`addressCountry` 均已正确落地对应国家（Togo, India, Belarus, Spain, Thailand, Bahrain, Ghana, United_Kingdom, France 等）。
    - `fusanhe_conversation`: 10 条对应 MIC 会话。
    - `fusanhe_message`: 94 条完整双向消息。

## 3. 安全与受限约束确认

- 全程保持 `FUSANHE_OUTBOUND_PAUSED=true`，未对外部买家发生任何真实网络发送。
- 所有报告与日志均严格脱敏，不输出敏感买家联系方式、原始消息内容与安全令牌。
