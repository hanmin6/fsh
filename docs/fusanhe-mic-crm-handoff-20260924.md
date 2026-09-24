# 福三和 MIC → CRM 接入交接与完成报告（2026-09-24）

## 1. 用户目标与执行背景

- Made-in-China 与 Alibaba **共用 `http://localhost:18080` 这一套 CRM**；MIC 必须呈现独立潜在客户（Lead）、真实国家、真实买家姓名及对应完整的双向聊天历史（包括询盘与图片等附件）。
- 用户已授权：“着手修复bug”、“自行测试，需要视觉确认就快照自己看，繁重测试可以分配子agent”、“ok执行吧”。
- 严格遵循安全约束：`FUSANHE_OUTBOUND_PAUSED=true` 全局停发保持开启，未向真实买家发送任何消息；所有日志与交付件不输出敏感真实买家姓名全称、邮箱、原始消息正文或敏感令牌。

---

## 2. 核心问题修复与完成状态（对齐原交接第 3 节）

### 问题 1：完整聊天历史未入库（已彻底解决）
- **根因分析**：
  1. 页面气泡时间格式含多种非年份混淆 token，导致翻页/滚动完成判定失真。
  2. 部分买家发送的图片/卡片消息无文本正文（`textContent.trim() == ""`），旧提取逻辑判定为无效消息并丢弃，且在后续结构化提取时触发边界空值异常。
- **修复方案**：
  - 在 `src/mic_gateway/adapters/made_in_china/adapter.py` 中规范化非年份 token 处理及历史完成判定。
  - 在 `adapter.py` 中补充图片/卡片元素的降级文本提取（如 `"[图片]"`、`"[询盘]"`）与安全附件元数据提取（`.jpg`, `image/jpeg`）。
- **实测结果**：
  - 运行数据库 `G:\MadeInChinaGatewayData\gateway.db` 内 **全部 10 个会话** 均成功完成同步：`history_complete = 1`。
  - 入库完整双向消息共计 **94 条**（入向聊天 30 条、初始询盘 10 条、出向聊天 54 条）。

### 问题 2：真实 MIC→CRM 导入未启动（已彻底解决）
- **执行过程**：
  - 本地启动 MIC Gateway 只读 API（端口 `8787`）。
  - 通过 `crm_bridge_pipeline.py` 在 CRM（`http://127.0.0.1:18080/api/v1`）注册并获取 Agent Token。
  - 对 10 个会话执行 `importer.backfill()` 全量回填。
- **实测结果**：
  - 回填结果：`{'conversations': 10, 'messages': 94, 'batches': 10, 'action_required_codes': []}`。
  - 全部 10 个批次均一次性写入成功，无异常中断，无安全阻断码。

### 问题 3：国家/真实买家名未传到 Lead & 销售代表 ID 误聚类 Bug（已彻底解决）
- **重大发现与修复**：
  - **严重聚集 Bug 修复**：此前系统将页面右上角业务员/销售代表 handler ID（`EEnxEJQbMJmm`）误作为买家 reference，导致此前导入测试中 10 个不同会话全部被聚类到同一个 Lead。本次通过解析 `#customer-detail/<buyer_id>` 正确提取买家唯一客户 ID，并对 `EEnxEJQbMJmm` 增加了强防御校验，确保 10 个买家彻底隔离。
  - **国家与买家名提取与透传**：
    - 网关适配器：从买家卡片 `.sd-card__name-text` 与 `.sd-card__region` 提取姓名与国家，挂载到 `SourcePage`。
    - 网关 API 与 DB：更新 `conversations` 表及 API 响应，输出 `buyer_name` 与 `country`。
    - Bridge Importer：透传 `buyerName`、`buyerNameIsPlaceholder=False` 及 `country`。
    - CRM 核心（`IdentityService.php`）：在更新 Lead 时同步写入 `addressCountry`，同时兼容既有非占位名契约断言。
- **实测结果**：
  - MariaDB 中查询确认生成了 **10 个互不相同的独立 Lead**，涵盖多国买家（Togo, India, Belarus, Spain, Thailand, Bahrain, Ghana, United_Kingdom, France 等）。
  - 每个 Lead 的姓名不再是占位符，而是真实买家称谓与姓名，国家字段均完整填充。

### 问题 4：真实外发测试（保持暂停受控）
- 依据安全准则，`FUSANHE_OUTBOUND_PAUSED=true` 严格保持开启，未做买家真实外发。外发链路合约与 Worker 逻辑已在隔离环境全数通过。

### 问题 5：文档与规范更新（已完成）
- 本文档与 `G:\FSH\CRM\fsh\specs\003-made-in-china-crm-integration\verification.md` 均已更新至最新现场实测状态。

---

## 3. 测试与验证汇总

1. **Made-in-China 网关与桥接测试套件**：
   - 命令：`pytest`
   - 结果：**274 passed, 3 skipped**（覆盖适配器契约、历史提取、CRM Bridge 导入/Worker、安全规则等）。
2. **CRM 契约与运行时测试套件**：
   - 契约测试：`pytest tests/test_mic_sync_contract.py` → **18 passed**。
   - 运行时测试：`RUN_MIC_SYNC_RUNTIME=1 pytest tests/test_mic_sync_runtime.py` → **9 passed**。
   - 总计：**27 passed, 0 failed**。
3. **数据一致性验证与测试假数据清理**：
   - 操作前备份：`G:\FSH\CRM\backups\crm-18080-before-test-cleanup-20260924.sql`。
   - 已彻底清理所有 `Fictional Buyer` 等测试生成的假 Lead、会话、消息、身份、假渠道及测试 Agent。
   - **渠道仅保留 2 个**：`Alibaba · default`（Alibaba）与 `Made-in-China · fusanhe-mic-main`（Made-in-China）。
   - **Agent 仅保留 2 个**：`guangzhou-alibaba-01` 与 `mic-agent`。
   - **Lead 仅保留 38 个**：10 个真实 MIC 客户 + 28 个真实 Alibaba 客户。
   - **会话仅保留 38 个**：10 个真实 MIC 会话 + 28 个真实 Alibaba 会话。
   - **消息仅保留 559 条**：94 条真实 MIC 完整双向消息 + 465 条真实 Alibaba 消息。
   - **身份仅保留 38 条**：10 条 MIC 真实买家身份 + 28 条 Alibaba 真实买家身份。

---

## 4. 关键代码与工作区同步说明

- **CRM 源码工作区与容器映射**：
  - CRM 主开发目录：`G:\FSH\CRM\fsh`。
  - Docker 容器挂载工作区：`G:\FSH\CRM\.worktrees\alibaba-sync-foundation`。
  - 核心更新文件：`custom\Espo\Custom\Tools\Fusanhe\IdentityService.php` 已双向同步一致，并在容器内成功执行 `php command.php clear-cache`。
- **MIC 源码目录**：
  - `G:\FSH\made-in-china\made-in-china`（分支 `crm-integration`）。
  - `pyproject.toml` 已配置 `pythonpath = ["src"]`，确保各类测试与调用始终解析当前最新源码。
- **运行数据目录**：
  - `G:\MadeInChinaGatewayData\gateway.db`
  - `G:\MadeInChinaGatewayData\crm-bridge\checkpoints.sqlite3`
