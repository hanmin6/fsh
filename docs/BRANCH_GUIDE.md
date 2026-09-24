# GitHub 分支地图与开发交接

核对日期：2026-09-24。本文只列出 `hanmin6/fsh` **远端的 7 个分支**，依据远端分支指针、提交祖先关系、实际文件和各阶段交接文档整理。本机其他 worktree 或仅存在于本地的分支不在此表。这里的“已并入”指该分支当前顶端提交是 `main` 的祖先；不代表该旧分支文档里的限制仍是当前限制，也不代表所有功能经过真实业务验收。

## 先看结论

| GitHub 分支 | 2026-09-24 顶端提交 | 与当时 `main` 的关系 | 用途 |
| --- | --- | --- | --- |
| [`main`](https://github.com/hanmin6/fsh/tree/main) | `99956dd` | 集成基线 | CRM、AI 客服、食品外贸骨架、非渠道生产准备和 Alibaba 同步基础 |
| [`codex/unified-inbox-mvp`](https://github.com/hanmin6/fsh/tree/codex/unified-inbox-mvp) | `09e0c62` | 已并入；独有提交 0 | 9 月 18 日统一询盘 MVP 快照 |
| [`codex/fusanhe-crm-frontend`](https://github.com/hanmin6/fsh/tree/codex/fusanhe-crm-frontend) | `8f5c406` | 已并入；独有提交 0 | 9 月 19 日前端工作台快照，末端也含 API 加固 |
| [`codex/backend-api-v1`](https://github.com/hanmin6/fsh/tree/codex/backend-api-v1) | `8f5c406` | 已并入；独有提交 0 | 9 月 19 日 CRM API 加固快照；与前端分支**同一提交** |
| [`codex/android-client-ui`](https://github.com/hanmin6/fsh/tree/codex/android-client-ui) | `20e94cc` | 已并入；独有提交 0 | 9 月 19 日 Android 1.0.0 UI 演示快照 |
| [`codex/release-crm-food-20260921`](https://github.com/hanmin6/fsh/tree/codex/release-crm-food-20260921) | `67174f6` | 已并入；独有提交 0 | 9 月 21 日 CRM/AI 客服与食品外贸集成发布点 |
| [`codex/boss-history-insights`](https://github.com/hanmin6/fsh/tree/codex/boss-history-insights) | `4f41f6f` | **尚未并入**；比当时 `main` 多 2 个提交 | 老板历史客户看板、匿名信号分析和开发交接 |

> 分支提交会继续变化。本表是 2026-09-24 的快照。查看实时差异时，以 GitHub 分支页和 `git rev-list --left-right --count origin/main...origin/<分支名>` 为准。前端/API 两个分支指向同一 SHA，不需要当成两份独立改动合并。

## `main`：当前集成基线

`main` 已包含早期统一询盘、前端/API、Android UI 和 9 月 21 日发布分支的提交。之后的 `0e509e2` 加入非渠道生产准备：Agent 独立凭据与轮换、请求追踪、备份校验、权限和知识扫描加固、Android 认证/远程仓库基础、Spec Kit 工程文档及验证。9 月 22 日的 `88b12d0`、`aec6cea`、`ffbcb44` 等提交加入 Alibaba 会话/消息幂等入库、Agent 鉴权、增量同步接口，以及 `alibaba-client/` 的浏览器采集、同步状态和发送执行端代码；`99956dd` 修正规格检查和换行配置。

主要入口：[项目 README](../README.md)、[项目状态（旧版本快照）](PROJECT_STATUS.md)、[非渠道生产准备验证](../specs/002-non-channel-production-readiness/verification.md)、[Alibaba 采集端说明](../alibaba-client/alibaba_messenger/README.md)、[CRM 同步服务](../custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php)、[运维手册](operations.md)。`make spec-check`、`make verify-offline` 是基础检查；运行时测试要使用隔离环境。

**当前边界：** `main` 有 Alibaba 采集和入库代码，不等于指定账号已完成真实全历史回填、覆盖率对账或真实平台发送验收。食品模块与 ERP/工厂/物流/财务尚未连接。`main` 目前**没有**老板历史客户页；那两次提交只在 `codex/boss-history-insights`。`README.md` 与 `PROJECT_STATUS.md` 的部分句子写于较早阶段，判断现状要结合本索引、代码及新验证记录。

## `codex/unified-inbox-mvp`：统一询盘 MVP

顶端 `09e0c62`，标签 `crm-mvp-v0.1.0`。这条早期里程碑建立 Docker/EspoCRM 基础（`d8cb6b2`）、统一询盘与 AI 回复流程（`5cf828f`）、操作和备份脚本（`67852a3`），最后在询盘列表增加响应时效字段。代码包括外部渠道、会话、消息、草稿、发送任务等元数据，`WorkflowService.php`、API 路由、Mock/占位连接器、会话详情和运营 Dashlet。

可从该分支的 [WorkflowService](https://github.com/hanmin6/fsh/blob/codex/unified-inbox-mvp/custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php)、[会话详情](https://github.com/hanmin6/fsh/blob/codex/unified-inbox-mvp/client/custom/src/views/external-conversation/record/detail.js)、[契约测试](https://github.com/hanmin6/fsh/blob/codex/unified-inbox-mvp/tests/test_contracts.py) 追溯。它主要展示 Mock 闭环；当时真实渠道连接还只是骨架。该分支已经是 `main` 的祖先，适合追溯最初 MVP，不应作为新的集成目标。当时文档有验证脚本，但本次分支审查没有重跑测试。

## `codex/fusanhe-crm-frontend`：前端工作台阶段

分支历史中的前端提交 `8790600` 到 `fd83145` 逐步建立品牌、登录与导航、统一询盘工作台、运营仪表盘、客户和审核视图、响应式布局；`fd83145` 带 `crm-web-v0.2.0` 标签。主要文件在 [`client/custom/src/views/fusanhe/`](https://github.com/hanmin6/fsh/tree/codex/fusanhe-crm-frontend/client/custom/src/views/fusanhe) 和 [前端说明](https://github.com/hanmin6/fsh/blob/codex/fusanhe-crm-frontend/client/custom/res/fusanhe/FRONTEND.md)。

顶端的 `8f5c406` 又加入了 API/渠道状态加固，所以这个分支名称不能解释为“只有前端”。前端文档记载当时的离线测试和页面检查，也明确真实平台记录、部分大数据/附件场景尚未验收；本次只核对提交，没有重跑。当前分支完全在 `main` 历史中，后续前端协作改动已在 `main` 继续演进。

## `codex/backend-api-v1`：CRM API 加固阶段

顶端同为 `8f5c406`，标签 `crm-api-v0.3.0`，与前端分支完全相同。此提交修复新客户入库的匹配状态和 Dashboard 只读计算，增加 `GET /Fusanhe/status`，收紧 Agent 任务领取、成功回执和重复回写，提供 Alibaba Bridge 的**只读健康状态**，并加入测试和 [API 交接](API_AGENT_HANDOFF.md)。可看 [当时的状态接口](https://github.com/hanmin6/fsh/blob/codex/backend-api-v1/custom/Espo/Custom/Tools/Fusanhe/Api/GetStatus.php)、[路由](https://github.com/hanmin6/fsh/blob/codex/backend-api-v1/custom/Espo/Custom/Resources/routes.json) 和 [回归测试](https://github.com/hanmin6/fsh/blob/codex/backend-api-v1/tests/test_p0_fixes.py)。

旧交接记载当时的 Docker、PHP 和接口测试；本次审查未重跑。该阶段的“缺少独立 Agent 凭据/真实同步”等待办是**9 月 19 日状态**，后续 `main` 已加入相应基础代码。Bridge healthy 只说明桥接服务状态，不证明历史消息读取完成。此分支无需再单独合并。

## `codex/android-client-ui`：Android 1.0.0 UI 演示

顶端 `20e94cc`，标签 `android-v1.0.0`。用 Jetpack Compose 做客户、历史、会话、消息、AI 建议与翻译等约 14 个主要界面，配有 Mock Repository、DTO/Retrofit/Room 占位和 [后端映射说明](../android-client/docs/BACKEND_API_MAPPING.md)。入口是 [Android README](../android-client/README.md)、[`ui/screens`](../android-client/app/src/main/java/com/fusanhe/crm/ui/screens) 和 [`data/mock`](../android-client/app/src/main/java/com/fusanhe/crm/data/mock)。

分支文档记载当时的构建与 lint 结果；本次审查未重跑。它是 UI/Mock 演示快照，不能代表已经能向真实客户发送消息。`main` 后来又加入认证、安全会话存储、远程仓库、DTO 映射和测试，所以要开发当前 Android 客户端应从 `main` 看，而非从此旧分支继续。

## `codex/release-crm-food-20260921`：CRM 与食品业务发布点

顶端 `67174f6`，同时是 `fusanhe-v0.5.0`、`crm-api-v0.5.0`、`crm-web-v0.4.0` 标签。这个发布点把 CRM/AI 客服第一阶段（双入口、共享身份、人工匹配、客服转销售、接管、草稿、Mock/真实任务隔离、停发保护）和食品外贸的五组业务骨架整合：产品/规格、证书/报告、样品、询价/报价/PI、订单/分批交付。食品功能有实体、布局、API、权限、状态机和 Feature Flag，默认隐藏。

[发布交接](RELEASE_HANDOFF_2026-09-21.md)和[第一阶段交接](PHASE1_ZCODE_HANDOFF.md)写有当时的测试、回退与限制。那些结果是发布时的记录，本次没有重跑。该分支已经完整进入 `main`；后续 Alibaba 同步基础不在这个 9 月 21 日发布点内。食品业务仍是 CRM 内的记录与流程，并未接通 ERP、工厂、物流或财务系统。

## `codex/boss-history-insights`：老板历史客户功能，尚待集成

这是当前唯一有 `main` 尚未包含提交的远端专题分支：`ec69444` 加功能，`4f41f6f` 加交接文档。从 `99956dd` 直接开发，当前比本索引写入前的 `main` 多 2 个提交。它新增 `#Home/insights` 只读页面、服务端搜索/分页和证据链接、上海当日规则建议；独立历史分析 Worker 只送固定词表的匿名信号，有 JSON/证据校验、缓存、失败重试、锁和每日调用预算；另有源端会话及消息 ID 集合对账命令，并改善同步失败恢复和日志脱敏。

从该分支的[开发交接](https://github.com/hanmin6/fsh/blob/codex/boss-history-insights/docs/DEVELOPMENT_HANDOFF_2026-09-24.md)、[老板演示说明](https://github.com/hanmin6/fsh/blob/codex/boss-history-insights/docs/BOSS_DEMO.md)、[任务清单](https://github.com/hanmin6/fsh/blob/codex/boss-history-insights/specs/003-boss-history-insights/tasks.md)、[验证记录](https://github.com/hanmin6/fsh/blob/codex/boss-history-insights/specs/003-boss-history-insights/verification.md)进入。核心代码是 [看板服务](https://github.com/hanmin6/fsh/blob/codex/boss-history-insights/custom/Espo/Custom/Tools/Fusanhe/BossInsightsService.php)、[前端页面](https://github.com/hanmin6/fsh/blob/codex/boss-history-insights/client/custom/src/views/fusanhe/insights.js)、[分析 Worker](https://github.com/hanmin6/fsh/blob/codex/boss-history-insights/custom/Espo/Custom/Tools/Fusanhe/HistoryAnalysisWorker.php)。

已有合成数据和隔离运行时验证，以及两次匿名合成模型调用。**真实 Alibaba 全历史回填仍为 0；平台总数和失败数未知。** 真实来源完整性清单、至少 20 个客户抽验、真实分析效果与模型实际费用、询价/索样优先规则及大数据性能尚未完成。`main` 的本索引不会把这些未合并功能写成主干已交付。

## 接手和维护规则

1. 开始新工作时先确认 `git branch --show-current`，看目标功能是否只在专题分支。不要把已是 `main` 祖先的五个历史分支再次合并。
2. 阅读目标分支**自身**的 README、规格、验证与最新提交。历史文档里的“当前”只对应当时日期；测试记录也只证明当次版本与环境。
3. 需要老板历史功能时从 `codex/boss-history-insights` 审查或提出 PR；在正式集成前，不把真实回填、全量对账和自动发送说成已验收。
4. 功能/契约变更遵循 [工程宪章](../.specify/memory/constitution.md)，维护对应 `specs/NNN-*` 的需求、计划、任务与验证。私密文档、`.env`、浏览器 Profile、客户原文清单和备份不进 Git；全局停发保持开启，除非有明确的受控发送任务。
