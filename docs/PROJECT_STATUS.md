# 福三和 CRM 项目状态

更新日期：2026-10-09。当前运行环境统一为 22005 Linux；22001 原 Windows 上的 Dify、渠道抓取、CRM bridge 与旧客服助手已迁移或退役清理。部署位置、SSH 与 noVNC、备份恢复及验收边界见 [迁移与运维记录](MIGRATION_22001_TO_22005_2026-10-09.md)。

当前 CRM HTTPS 为 `https://gzfusanhesp.com/`。已部署客户联网评级、产品视频素材流程，以及消息中心关联客户评级、右侧客户背调、评级排序、英文自动中文翻译。Dify 为 3 个知识库、41 份文档、9 份工作流；Alibaba 登录 ready、MIC 会话 healthy，采集进程与 CRM 容器健康。全局停发保持开启，历史完整性对账和长期增量观察仍按证据验收。

本次 GitHub 同步将当前开发分支 `codex/muse-crm-mcp` 的已部署代码与迁移资料一起保存；`main` 的历史发布基线仍需通过合并记录追溯，不能把历史快照中的“尚未部署”当成当前状态。


历史发布记录：2026-09-30，Web 正式版本为 [`crm-web-v1.1.0`](https://github.com/hanmin6/fsh/tree/crm-web-v1.1.0)，`main` 是唯一正式前端基线。统一五页 UI 已整合 HIG 能力，新增独立文本与视频通道；静态图片生成关闭。独立验收与 GitHub CI 通过，本次只发布 GitHub，尚未部署服务器。当前状态见 [1.1.0 发布交接](RELEASE_CRM_WEB_1.1.0.md)、[验收记录](../specs/006-dual-ai-gateways/verification.md)及 [分支索引](BRANCH_GUIDE.md)。

以下保留历史快照，旧版本号、分支表和完成度用于追溯。

更新时间：2026-09-24。本页主体是 **2026-09-21 的版本基线快照**，其中完成度百分比和“未接入”描述不代表 9 月 24 日的现状。接手开发请先看 [最新开发交接](DEVELOPMENT_HANDOFF_2026-09-24.md)；老板历史客户功能的实测状态见 [演示说明](BOSS_DEMO.md)和 [003 验证记录](../specs/003-boss-history-insights/verification.md)；Made-in-China 客户端与回填集成见 [MIC 交接说明](fusanhe-mic-crm-handoff-20260924.md)。


## Spec Kit 治理基线

项目已在仓库根目录接入 Spec Kit。全系统业务基线位于
[`specs/001-system-baseline/spec.md`](../specs/001-system-baseline/spec.md)，设计、契约、验证与未完成任务均在同目录。

- 下文“已完成资产”和“当前验证证据”是已验证基线。
- “下一阶段优先级”与 `specs/001-system-baseline/tasks.md` 的未勾选项是未完成目标，不构成已交付声明。
- 后续行为变更必须新建有边界的 `specs/NNN-feature-name/` 目录，不直接把新实施范围堆入基线。

## 当前版本基线

| 组件 | 版本 | 当前状态 |
| --- | --- | --- |
| Docker 基础环境 | CRM MVP 0.1.0 | 本地可运行 |
| Web 工作台 | CRM Web 0.4.0 | 双模块入口与协作工作台完成，食品模块以原生实体布局交付 |
| CRM 自定义 API | CRM API 0.5.0 | MIC sync API 已实现并通过离线/隔离验证；完整历史、目标身份及真实发送未通过现场验收 |
| Android 客户端 | Android 1.0.0 | UI/Mock 完成；客户、会话、消息读取与 AI 草稿真实数据底座已接入 |

## 已完成资产

- 4 个健康运行的 Docker 服务：MariaDB、EspoCRM、daemon、websocket。
- CRM/AI 客服共享客户身份、身份确认、客服转销售、人工接管、人工草稿、回复快照和 Mock/真实执行隔离。
- 5 组食品外贸业务模块：产品/规格、证书/报告、样品、询价/报价/PI、订单/分批交付；默认由 Feature Flag 隐藏。
- 20+ 个自定义业务接口，覆盖双模块协作和食品外贸工作流。
- Web 登录、导航、首页、询盘、会话、客户、草稿、知识库、发送任务和执行端视图。
- AI 草稿、人工批准、幂等任务、Agent 领取、失败重试和发送结果回写 Mock 闭环。
- Android 14 个主要页面、完整 Mock Repository，以及显式可切换的真实 DTO/Mapper/Remote Repository。
- Android 客户新增、历史时间线、会话、翻译、AI 建议和异常状态演示。
- 接口交接、权限、Android 后端映射、备份恢复和版本记录文档。

## 完成度判断

以下比例用于规划，不是验收承诺：

| 范围 | 估算完成度 | 说明 |
| --- | ---: | --- |
| 本地演示 MVP | 90% | Web、后端 Mock 闭环、食品模块和 Android UI 均可演示 |
| Web 工作台 MVP | 92% | CRM/AI 客服核心页面完成，食品模块主要使用原生实体布局 |
| CRM 接口层 | 82% | 协作与食品业务接口已具备 ACL/状态机，真实渠道与 Schema 仍待完善 |
| 食品外贸业务骨架 | 75% | 产品到订单/交付的 CRM 工作流完成，ERP/工厂/物流连接未做 |
| Android 1.0 UI 范围 | 100% | 约定的 UI 和 Mock 功能已完成并成功构建 |
| Android 生产接入 | 70% | 个人认证、加密会话、真实客户/会话/草稿、401 清理完成；分页/WebSocket/完整离线缓存待后续 |
| 真实渠道接入 | 持续验收中 | MIC CRM 导入与出向 Worker 代码已实现；现场历史与真实发送未验收。Alibaba 消息同步已有隔离验证，真实外发未验收 |
| 生产部署准备 | 85% | CI、Agent 凭证轮换、请求追踪、备份完整性和运维手册完成；正式监控平台与生产演练待部署 |

## 当前验证证据

- `docker compose config --quiet` 通过。
- EspoCRM `rebuild` 与 `app-check` 通过。
- 全部自定义 PHP 文件通过 PHP 8.3 语法检查。
- 8 项既有接口测试通过 7 项，远程 Alibaba 集成测试默认跳过 1 项。
- 发布分支食品模块契约测试、状态机回归和运行时闭环通过；停发默认保持开启。
- 非渠道生产化离线契约 45/45 通过；隔离 EspoCRM 运行时 12/12 通过，请求 ID 关联场景单独通过。
- Android `testDebugUnitTest lintDebug assembleDebug` 通过，包含 DTO Mapper、会话与 MockWebServer HTTP 契约测试。
- Android Debug APK 版本：`1.0.0`，最低 Android API 26。

### Made-in-China 当前验收边界（2026-09-24）

- MIC bridge 提供 `register`、`backfill`、`once`、`daemon`、`status`、`resolve-pending`，出向 Worker 提供 `run_worker --once/--interval`。生产运行与回滚步骤见 [`docs/operations.md`](operations.md#made-in-china-桥接运维) 和 [`docs/API_AGENT_HANDOFF.md`](API_AGENT_HANDOFF.md#2026-09-24-made-in-china-集成状态)。
- MIC Gateway Python 3.12 离线验证：269 passed、2 deselected；Ruff 与 mypy 干净。
- CRM MIC+Alibaba 离线契约：39 passed、16 skipped（运行时门禁未开启时）；隔离 MIC+Alibaba runtime：16/16 通过；PHP lint 和 Web 前端 13/13 通过。
- 合成跨系统桥接验收：`tests/integration/test_crm_bridge_runtime.py` 1/1 通过，真实 CRM client/importer/state 对接 loopback 隔离 CRM，MIC source 为 fake read data。注册、backfill、once/replay、入 Lead、sender/附件 metadata 读回通过；未建草稿/任务且全局停发保持开启。它不访问真实 MIC 页面。
- MIC Gateway `0001_initial → 0002_message_history` 在实时数据库的一致性备份副本迁移通过，保留 10 conversations、10 messages、1 Outbox；10 个旧 conversation 的 `history_complete` 都是 false。原运行数据库未在该验证中迁移。
- 已保存 DOM 快照提供唯一可见的 `inquiry-id` 会话标记，代码据此校验；真实页面的完整历史翻页及身份标记仍待现场验证。同步对未确认身份/完整度 fail closed。指定目标真实发送尚未执行，继续保持 `FUSANHE_OUTBOUND_PAUSED=true`。
- 出向 Worker 的 uncertain/结果含糊场景只进入人工对账；不得盲目重发。回滚停 MIC bridge/Worker 并保留已导入记录、审计、检查点和对账日志。

## 下一阶段优先级

### P0：上线动作

1. 在生产发布前轮换 Bridge、管理员和 Agent 注册引导凭证。
2. 在隔离生产副本执行完整恢复演练，并接入正式日志/告警平台。
3. 为正式域名构建 `FUSANHE_USE_REMOTE=true` 的签名 Android 包并完成权限验收。

### P1：Android 接入

1. 接入 Room 完整离线缓存、分页、WebSocket 和冲突解决。
2. 补齐远程客户历史、通知和翻译接口。
3. 增加 UI/E2E 测试与正式签名发布流程。

### P1：真实渠道

1. 实现 Alibaba 消息增量同步、Webhook 签名验证和真实发送。
2. 实现独立站、邮件和 Made-in-China 连接器。
3. 建立死信、重试、游标、限流、监控和补偿任务。

## 分支职责

| 分支 | 职责 |
| --- | --- |
| `main` | 已验证的本地集成基线 |
| `codex/fusanhe-crm-frontend` | Web 与 CRM API 基线 |
| `codex/backend-api-v1` | CRM API 0.3.0 里程碑 |
| `codex/android-client-ui` | Android 1.0.0 开发与发布基线 |
| `codex/unified-inbox-mvp` | 历史 MVP 里程碑，只保留追溯 |

当前仓库已连接私有 GitHub 远端 `https://github.com/hanmin6/fsh.git`。发布完成后保留 `main`、发布分支和组件标签；真实渠道与 Android 接入仍按后续阶段推进。

## 2026-09-24 老板历史客户演示增量（003）

已新增 `#Home/insights`：真实同步来源会话的服务端搜索/分页/状态筛选、身份提示、原始客户/会话/消息链接、上海当日规则建议、分析证据与失败/过期状态。新增独立分析 worker（匿名固定词表输入、无 Mock、同源版本缓存、文件锁、每日 100 次调用预算、失败重试与审计），以及平台 ID 集合对账命令。修复旧 dashboard 未定义过滤条件与上海日期，限制本人权限统计；回填失败保留可恢复状态，同步日志不回显姓名/异常原文。

本机演示库仍为 **0 条真实历史导入，0 条客户分析，0 条今日建议**；平台可见总量及未导入失败数未知。用户指定“福三和——主机”已连通，桥接 OAuth 有效，尚待确认实际 Alibaba 登录入口并安装/复用历史采集端。没有真实回填或 20 客户抽验，不宣称全量导入完成。产品/原文业务语义仍待人工核验；当前分析仅使用匿名规则信号。

详见 `docs/BOSS_DEMO.md`、`specs/003-boss-history-insights/verification.md`。全局停发保持开启，未向客户发送消息。

### 2026-10-03 CRM 触达证据与 AI 背调（009）

CRM 已新增 `OutreachEvidence` 与 `ProspectResearch`：支持受控 PNG/JPEG/WebP 截图的私有存储、客户快照、平台消息 ID、发送状态、幂等回放、ACL 读取和 AI 背调结果。客户详情工作台新增“主动触达”页签，可查看截图、发送内容、来源和背调状态，并手动发起联网研究。

本阶段不接 Muse、不浏览社交平台、不创建 `OutboundTask`、不发送外部消息。Muse 上传适配、社交平台执行器和每日外发配额留待后续特性。
