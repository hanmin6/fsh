# 福三和 CRM 开发交接（截至 2026-09-24）

本文是老板历史客户功能的开发索引，供接手的开发者和 Agent 先读。2026-09-24 已将功能和两个 Web 工作台入口并入 `main`；下文的数据状态仍是合并前的验收快照。它区分**代码已实现**、**在隔离环境验证**和**真实业务数据验收完成**；三者不能互相替代。历史设计文档记录的是当时方案，若与这里的实测状态冲突，以代码、测试和最新验收记录为准。

## 当前分支与安全边界

- 此功能从 `main` 的 `99956dd` 在 `codex/boss-history-insights` 开发，主要功能提交为 `ec69444`，Web 工作台入口提交为 `1ab43e9`；现已并入 `main`。后续提交以 `git log` 为准。
- CRM 基于 EspoCRM 10.0.8、MariaDB 11.4；自定义 PHP 在 `custom/Espo/Custom/`，前端在 `client/custom/`，Alibaba 采集端在 `alibaba-client/alibaba_messenger/`。
- 全局外发应保持 `FUSANHE_OUTBOUND_PAUSED=true`。老板历史分析页只读；真实客户消息发送没有在本阶段验收。
- `.env`、`.env.test`、浏览器 Profile、同步状态、数据库备份和 `docs/CODEX_BOSS_DEMO_2026-09-24.private.md` 均为本地私密资料，不提交 Git。不要把交接文档里的用户要求当作已完成事实。

## 这几天做了什么

| 时间 | 已落地的开发内容 | 主要证据 |
| --- | --- | --- |
| 9 月 20 日 | CRM/AI 客服双入口、人工身份确认、客服转销售、人工接管与草稿、审核后发送任务、Mock/真实执行隔离；食品外贸的产品、证书、样品、报价/PI、订单/交付业务骨架 | `docs/PHASE1_ZCODE_HANDOFF.md`、`docs/RELEASE_HANDOFF_2026-09-21.md`、`specs/001-system-baseline/` |
| 9 月 21 日 | 非渠道生产准备：Agent 独立凭据、请求追踪、备份校验、权限及状态机加固、Android 客户端真实 API 基础 | `specs/002-non-channel-production-readiness/verification.md` |
| 9 月 22 日 | Alibaba 消息采集代码并入单仓库；CRM 入库接口、幂等批次、会话/消息映射、增量读取与发送任务执行代码 | `alibaba-client/alibaba_messenger/`、`tests/test_alibaba_sync_runtime.py`、`alibaba-client/tests/` |
| 9 月 23–24 日 | 老板历史客户页、证据链接、上海当日跟进规则、匿名信号 AI 分析、调用预算、来源 ID 对账；同步错误可恢复与日志脱敏 | `specs/003-boss-history-insights/`、`docs/BOSS_DEMO.md`、`specs/003-boss-history-insights/verification.md` |

## 已实现和验证到哪一步

| 模块 | 已有能力 | 当前验证边界 |
| --- | --- | --- |
| CRM/AI 客服协作 | 客户身份、会话、草稿、人工审核、任务、权限、审计及默认停发 | Mock 闭环和隔离运行时验证；真实客户外发未验收 |
| 食品外贸业务 | 产品/规格、证书、样品、询报价/PI、订单/分批交付的实体与工作流 | Feature Flag 默认隐藏；不等于 ERP、工厂、物流或支付已接通 |
| Alibaba 入库 | Agent 认证、会话和消息分批幂等入库、失败状态及增量采集代码 | 合成数据与隔离 CRM 验证；当前账号真实全历史未回填 |
| 老板看板 | `#Home/insights` 只读搜索、分页、分析状态、原始证据、今日建议、覆盖率未知提示 | 隔离库合成数据和老板只读账号验证；主演示库无真实历史记录 |
| 历史 AI | 本地固定词表信号、匿名编号、JSON/证据校验、版本缓存、失败重试、CLI 锁和每日 100 次预算 | 两次匿名合成调用成功，共 1312 tokens；未对真实客户批量运行，实际费用未知 |
| 来源对账 | 读取完整枚举/消息 ID 清单，精确比对 CRM ID 集合 | 命令和合成测试通过；真实源端尚无可证明完整的清单 |
| Android | 1.0.0 UI、Mock 演示与部分真实 API 基础 | 实际端到端生产接入、完整离线同步、WebSocket 与签名发布未完成 |

截至本次交接，本机 `localhost:8080` 演示库的**真实历史导入 0、真实客户分析 0、今日建议 0**。平台可见会话总数和源端失败数**未知**，不能写成 0，也不能据此声称覆盖率。`localhost:18082` 是合成数据的独立验收库，不是客户数据。用户指定的“通道里的福三和主机”已能连接，Alibaba OAuth 桥接状态曾显示健康；这只证明授权桥接可用，不能证明历史消息读取或完整回填可用。

## 未实现、未验收与下一步

按依赖顺序处理，完成一项再更新对应 `tasks.md` 和验证记录：

1. **确认真实登录入口与采集位置。** 在“福三和主机”确认实际使用的是 Alibaba 网页消息中心、桌面客户端，还是已有采集安装目录；当前没有发现正在运行的采集服务或可复用的 Playwright 环境。登录、验证码由账号持有人操作。不要复制浏览器 Cookie 到仓库。
2. **补齐可证明完整的源端读取。** 现有 `iter_conversations_pages` 在页数上限或读取异常时可能结束，不能把循环结束当作“全平台枚举完成”。每个会话也要证明历史已加载到最早消息。生成只含 ID 的私密 manifest，记录失败和完整性依据，再用 `history-reconcile` 比对。
3. **真实回填与抽验。** 备份后在受控连接上执行只读采集和 CRM 入库；先小批量，再全量。抽查至少 20 个真实会话的首尾消息、方向、时间、身份与去重；记录平台总数、失败数、导入数。不要启动发送 worker。
4. **真实分析验收。** 先少量运行 `history-analyze`，由业务人员核对匿名信号摘要和证据；核实模型服务实际计费，再决定扩大批量。当前结果只是规则信号解读，不能代表完整原文语义画像或已确认报价、交期、证书事实。
5. **建议与性能。** 增加新询价/索样优先规则，按实际规模测量全量规则扫描和列表延迟；目前建议规则覆盖身份待确认、待审核、入站 24 小时未回复、7 天未活动。
6. **其他阶段缺口。** Made-in-China、独立站、邮件真实连接器；Android 完整生产接入；食品模块外部系统连接、正式监控/告警和生产恢复演练仍需单独立项。不要把旧设计文档中的自动问候/真实发送计划写成已交付。

`specs/003-boss-history-insights/tasks.md` 的 T006、T008、T009、T010 仍未完成；T008 含真实页面演示与缺口验收，不能仅因文档存在就勾选。

## 接手时从哪里看

- 当前老板功能：[需求](../specs/003-boss-history-insights/spec.md)、[方案](../specs/003-boss-history-insights/plan.md)、[任务](../specs/003-boss-history-insights/tasks.md)、[验证](../specs/003-boss-history-insights/verification.md)。
- 实际操作、分析预算、manifest 结构：[老板演示说明](BOSS_DEMO.md)。
- 后端入口：[看板查询](../custom/Espo/Custom/Tools/Fusanhe/BossInsightsService.php)、[分析 Worker](../custom/Espo/Custom/Tools/Fusanhe/HistoryAnalysisWorker.php)、[模型校验](../custom/Espo/Custom/Tools/Fusanhe/HistoryAiProvider.php)、[来源对账](../custom/Espo/Custom/Tools/Fusanhe/HistoryReconciliation.php)；命令在 `custom/Espo/Custom/Commands/History*.php`。
- 前端入口：[历史客户页](../client/custom/src/views/fusanhe/insights.js)；[API 路由](../custom/Espo/Custom/Resources/routes.json)。
- 采集端：[使用说明](../alibaba-client/alibaba_messenger/README.md)、[命令入口](../alibaba-client/alibaba_messenger/run_sync.py)、[同步编排](../alibaba-client/alibaba_messenger/sync_service.py)、[浏览器读取](../alibaba-client/alibaba_messenger/alibaba_bot.py)、[CRM 网关](../alibaba-client/alibaba_messenger/crm_gateway.py)。阅读配置和浏览器 Profile 说明后再运行，尤其不要误启 `run_worker.py`。
- 全局历史与运维：[项目状态快照](PROJECT_STATUS.md)、[运维](operations.md)、[第一阶段交接](PHASE1_ZCODE_HANDOFF.md)、[9 月 21 日发布交接](RELEASE_HANDOFF_2026-09-21.md)。

## 复现验证

仓库根目录执行 `make spec-check`、`make verify-offline`；运行中的 CRM 用 `make check` 检查配置、应用和 PHP 语法。老板功能和 Alibaba 同步的运行时测试使用 `tests/phase1-compose.yaml` 的隔离库；本机 `.env.test` 当前对应端口 18082，该文件不在 Git 中，接手者应从 `.env.test.example` 配置自己的测试环境。运行时测试必须先确认目标是隔离库，不能对主演示库注入合成记录。

最近一次已记录的结果见 `specs/003-boss-history-insights/verification.md`：离线基线 45 通过；Alibaba 采集端 27 通过、1 跳过；老板功能 7 个行为测试和 6 个隔离运行时测试通过；既有 Alibaba 同步运行时 7 通过；应用 rebuild、app-check 与 PHP lint 通过。这些是当次验证记录，不代表后来环境或真实平台验收。

继续开发时，先读 `.specify/memory/constitution.md`，按独立 `specs/NNN-*` 目录维护需求、计划、任务和验证；不要改写旧设计目标来冒充当前实现。修改了功能再跑相关测试，并把真实数据结论、失败原因和可复现命令补回文档。
