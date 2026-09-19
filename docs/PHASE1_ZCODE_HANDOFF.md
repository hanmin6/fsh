# 第一阶段交接文档（PHASE1_ZCODE_HANDOFF）

完成时间：2026-09-20
执行者：ZCode（自主实施）

## 1. 基线与位置

| 项目 | 值 |
|---|---|
| 基线 HEAD（main） | `b40f176` |
| 工作分支 | `codex/crm-ai-phase1-zcode`（自基线新建，未改动其他分支） |
| Worktree 绝对路径 | `/Users/hanming/Desktop/fusanhe-crm-phase1-zcode` |
| 最终 HEAD | 见 `git log -1`（本文档提交即最终提交） |
| 原工作目录 | `/Users/hanming/Desktop/福三和crm`（未做任何改动；其中的未提交架构图文件保持原样） |

## 2. 本地提交列表

| 提交 | 目的 |
|---|---|
| `f5938d9` | docs: 实施计划与已核实事实清单（PHASE1_ZCODE_PLAN.md） |
| `632b62b` | feat(metadata): ExternalIdentity 实体、controlMode、mock 隔离、转销售幂等键、枚举追加与中英文语言包 |
| `ee676fe` | feat(services): 身份映射、接待控制、销售转交服务与 WorkflowService 加固（intake 不建 Lead、知识过滤、快照、执行模式、停发一致性、人工草稿） |
| `cc45d94` | feat(api): 8 个新路由 + 既有接口 ACL 收紧 + 扫描器变更重审 + 角色补 Task/ExternalIdentity |
| `dee7e05` | feat(frontend+tests): 双模块入口、会话工作台协作区、客户详情分工、列表徽章、前端与离线契约测试 |
| `a9e7545` | test: 隔离环境运行时验收套件（14 项场景）与 searchParams 兼容说明 |
| `a33fd63` | fix: 补 ExternalIdentity Record 控制器（缺失导致 REST 404） |
| `5af8fb0` | fix: 独立审查修复（发送结果死锁、按钮锁死、approve 实体 ACL、人工草稿丢稿、动态停发横幅、closed 重开、停用渠道） |
| 最终提交 | docs: 本交接文档与 CHANGELOG |

无 push、无 rebase、无强推、无合并 main。

## 3. 功能与关键文件

### A. 双模块入口
- `#Home`：入口选择页（两张模块卡片 + 实时外发开关状态 + 权限内计数）。
- `#Home/crm`：CRM 工作台（客户/联系人/线索/我的待办；商机保留原生导航）。
- `#Home/service`：AI 客服工作台（统一收件箱、待审核草稿、身份待确认、发送异常；渠道/执行端按角色显示）。
- 文件：`client/custom/src/controllers/home.js`、`views/fusanhe/home.js`、`crm-home.js`、`service-home.js`。
- 旧路由（#ExternalConversation、#Account 等）全部保留兼容。

### B/C. 未建档接待与人工身份确认
- 实体 `ExternalIdentity`：唯一键 `identityKey` = `渠道类型|渠道账号实例|uid:/email:/phone:/anon:<会话外部ID>`；匿名访客按会话独立，绝不合并。
- intake 不再自动创建 Lead；返回 `identityId/needsManualMatch/createdLead:false`。
- 候选查询仅强匹配（邮箱/电话精确），逐条 `checkEntityRead` 过滤；确认关联/建档均为显式动作，服务端校验会话 edit + 目标 read/create + 身份 edit，审计记录操作者、来源与前后关联。
- 接口：`GET /Fusanhe/identity/:id/candidates`、`POST .../link`、`POST .../create-customer`。
- 文件：`Tools/Fusanhe/IdentityService.php`、`WorkflowService::intake/findChannel/attachIdentityToConversation`。

### D. 客服转销售
- `POST /Fusanhe/conversation/:id/handoff`：原生 Task（parentType=ExternalConversation）、幂等键 `Task.fusanheHandoffKey`（唯一索引）、校验会话 read + Task create + `checkAssignmentPermission` + `checkEntityCreate`；重复请求返回同一任务（`deduplicated:true`）。
- `GET .../handoff-tasks` 列出已建任务。

### E. 客户详情协作
- `customer-detail.js`：客户负责人与会话接待人分列显示；客户↔会话双向跳转（复用既有实现）。

### F. 状态拆分与人工接管
- `ExternalConversation.controlMode`（aiAssist/human，默认 aiAssist）；`status` 追加 `replied`，不再新写 sending/sent/failed（历史值保留可显示）。
- `POST /Fusanhe/conversation/:id/control`：接管/恢复，服务端校验 + 审计。
- 发送门槛统一在 `ControlService::assertSendAllowed`，claim 与 markSending 两处一致拦截停发与人工接管；已交给渠道的任务其结果回写不受接管阻断（记账而非发送），避免任务永久卡死在 sending。
- `POST /Fusanhe/task/:id/cancel`：取消未发送任务；sending 拒绝取消（结果未知）。

### G. 回复与 Mock 闭环
- 人工草稿：`POST /Fusanhe/conversation/:id/manual-draft`，与 AI 草稿走同一审核/批准/任务流。
- 快照：批准时最终文本写入 `OutboundTask.contentSnapshot`，领取 payload 从快照读取；旧任务回退 payload.body → 草稿文本。
- 隔离：`OutboundTask.executionMode`（mock/real，渠道 config.realOutbound 决定）× `AutomationAgent.mode`（mock/real）；Mock 执行端只能领 Mock 任务。
- 模拟回执：出站消息 `deliveryStatus=mockSent`，前端显式提示"不代表真实客户已收到"。
- 停发横幅动态读取 `GET /Fusanhe/status` 的 `outboundPaused`（60 秒缓存）。

### H. 知识安全与权限
- 知识过滤：`approvalStatus=approved` + `effectiveFrom/effectiveTo` 有效窗口 + 逐条 `checkEntityRead`；取前 5 条。
- `KnowledgeScanner`：checksum 变化将 approved 文档重置为 draft（重新审核）。
- 全部自定义接口补 ACL（intake/generate-draft/scan/dashboard/status 原先仅登录即可）；approve 增加草稿与会话实体级 read 校验。
- 状态机 Hooks（`custom/Espo/Custom/Hooks/`）：AIReplyDraft（批准后不可改、approved/sent 仅服务可写）、OutboundTask（仅服务可建可改关键字段）、ExternalConversation（发送态/controlMode/identity 服务专用）、ExternalMessage（出站消息仅服务可建）。服务层以保存选项 `fusanheService=true` 豁免。
- 审计：所有业务动作记录真实操作者（`draft.generated` 不再写 `current`）。

## 4. 数据模型变更、兼容与回退

**变更（全部增量）**：新实体 ExternalIdentity；ExternalConversation +identity/+controlMode、status 追加 replied；ExternalChannel +accountHandle；OutboundTask +executionMode/+contentSnapshot；AutomationAgent +mode；Task +fusanheHandoffKey（唯一索引）、parent 实体列表追加；ExternalMessage deliveryStatus 追加 mockSent。未删除任何字段或枚举值。

**兼容规则**：
- 旧会话（无 identity）：intake 新消息时自动补建映射；详情页显示"历史数据"提示。
- 旧渠道（accountHandle NULL）：按 `default` 归一匹配，行为不变。
- 旧任务（无 contentSnapshot）：领取正文回退 payload.body → 草稿文本。
- 旧会话状态 sent/sending/failed：正常显示，列表计入已回复；不允许通过 CRUD 新写。
- 角色数据：bootstrap.py 为四个角色补 Task 与 ExternalIdentity 授权（EspoCRM 中角色未列出的实体=无权限；此前业务员/主管/老板对 Task 实际无权限）。

**回退**：不合并分支即无影响。若已在某环境部署后回退：切回原代码并执行 `bin/command rebuild` 即可；新增的列/表残留无害。测试环境整体回退见第 8 节（直接 down -v 删除独立项目）。

## 5. 测试命令与真实结果

全部在隔离环境（fusanhe-phase1-test，见第 8 节）真实执行：

| 套件 | 命令 | 结果 |
|---|---|---|
| 离线契约+结构 | `python3 -m unittest tests.test_phase1 tests.test_contracts` | **26 通过** |
| 前端离线 | `node --test client/custom/tests/frontend.test.cjs` | **12 通过** |
| PHP 语法 | 容器内 `find custom -name "*.php" \| xargs -n1 php -l` | **全部通过**（29+9 个文件） |
| 运行时验收（停发=true） | `python3 -m unittest tests.test_phase1_runtime.Phase1Runtime` | **11 通过** |
| 运行时发送闭环（停发=false，仅隔离环境） | `python3 -m unittest tests.test_phase1_runtime.Phase1SendLoop` | **1 通过** |
| 既有接口测试 | `python3 -m unittest tests.test_p0_fixes` | **3 通过**（第 1 项断言按新产品规则反转：不再自动建 Lead，已注明理由） |
| 既有闭环验证 | `python3 tests/verify_runtime.py` | **2 通过**（按新规则更新：replied/mockSent/比率断言，已注明理由） |
| Mock Agent 脚本 | `python3 scripts/mock-agent.py` | **通过**（领取→发送→回写 sent） |
| Alibaba 远程集成 | `python3 -m unittest tests.test_alibaba_connector` | **跳过**（按设计需 RUN_ALIBABA_INTEGRATION_TESTS=1；未执行远程调用） |

**验收矩阵 14 项全部有运行时或离线证据**（对应关系见 `docs/PHASE1_ZCODE_PLAN.md` 第 8 节与测试方法名）。

**重要环境事实（已写入测试注释）**：EspoCRM 10 的列表接口会静默忽略 JSON 字符串形式的 `where` 查询参数，必须用 `searchParams` 或数组语法；`total` 字段在部分查询下不反映过滤条件，测试断言一律基于列表内容。前端 Espo Ajax 客户端不受影响。

## 6. 隔离环境演示七个核心协作场景

环境准备（全新隔离栈，不影响 fusanhe-crm 原项目）：

```bash
cd /Users/hanming/Desktop/fusanhe-crm-phase1-zcode
cp .env.test .env.test   # 已含虚构测试凭据
docker compose -p fusanhe-phase1-test --env-file .env.test -f tests/phase1-compose.yaml up -d --wait
docker compose -p fusanhe-phase1-test --env-file .env.test -f tests/phase1-compose.yaml exec -T espocrm bin/command rebuild
set -a; . ./.env.test; set +a
ESPOCRM_API_URL=http://localhost:18080/api/v1 python3 scripts/bootstrap.py
```

打开 http://localhost:18080（admin / phase1-test-admin-password），或直接运行验收脚本演示全部场景：

```bash
# 场景 1-5、8（身份、幂等、不合并、候选越权、双向跳转、转销售幂等、负责人分工、权限墙、知识门、错误反馈）
python3 -m unittest tests.test_phase1_runtime.Phase1Runtime -v
# 场景 6-7（接管阻断 + Mock 闭环与模拟回执）：需临时将 .env.test 中 FUSANHE_OUTBOUND_PAUSED=false 并重建 espocrm 后运行
python3 -m unittest tests.test_phase1_runtime.Phase1SendLoop -v
# 演示完恢复 FUSANHE_OUTBOUND_PAUSED=true 并重建
```

七个场景与界面操作对照：
1. **陌生访客接待**：AI 客服工作台 → 演示导入（`POST /Fusanhe/mock/intake`）→ 会话出现在统一收件箱，无 Lead 被创建，身份显示"待确认"。
2. **人工身份确认**：打开会话 → 身份确认卡 → "查找匹配客户"（仅邮箱/电话强匹配且在权限内）→ "确认关联"；或"建立线索建档"。
3. **客服转销售**：会话右栏"转销售跟进" → 摘要/负责人/截止 → 创建；重复点击返回同一任务；任务页可跳回来源会话。
4. **人工接管**：会话右栏"人工接管" → 审计记录 + 未发送任务被领取/发送两端拦截；"恢复 AI 辅助"还原。
5. **人工草稿**：会话右栏"人工草稿" → 撰写 → 保存 → 与 AI 草稿同样编辑/批准/拒绝。
6. **批准与快照**：批准草稿（二次确认 + 勾选人工审核）→ 任务保存不可变快照；已批准草稿无法再改。
7. **Mock 闭环与模拟回执**：隔离环境临时关停发 → mock-agent.py 领取/回写 → 出站消息带"模拟已发送"徽章与提示，会话状态"已回复"；全局停发恢复 true 后执行端领不到任何任务。

## 7. 待完成事项、已知限制与建议下一步

**已知限制（记录在案，未在本阶段处理）**：
- 领取租约 5 分钟与真实渠道发送耗时的 TOCTOU 窗口（租约到期重排为非原子，极端情况下可能重复发送）；真实渠道接入时需改为条件更新。
- 停发开关的动态横幅依赖 `GET /Fusanhe/status`（60 秒缓存）；该接口会触发占位连接器健康检查。
- AI 上下文已包含负责人与客户资料，但"已确认商务信息"目前仅指已审核知识，不含会话内人工确认的结构化商务字段。
- 知识检索仍为"前 5 条"，未按产品/语言/相关性排序（原 P1 技术债）。
- EspoCRM 标准列表/详情原生视图对自定义枚举的翻译依赖自定义视图，未逐屏核验。
- 浏览器端到端 UI 操作未自动化（隔离环境仅 API 级验证 + 前端离线测试）；页面渲染请按第 6 节在本地人工过一遍。

**建议下一步**：
1. 把 `bootstrap.py` 角色更新应用到生产前，先在灰度环境确认 Task/ExternalIdentity 授权符合组织预期。
2. 渠道接入时为 ExternalChannel.config 设置 `realOutbound: true` 并以 `mode=real` 注册执行端（Mock 隔离自动生效）。
3. 将"前 5 条知识"升级为按产品/语言检索（原交接文档 P1）。
4. 领取租约改条件更新 + 租约时长可配置。
5. 为身份确认增加操作员备注字段与二次复核流程（可选）。

## 8. 测试容器与卷（精确名称与状态）

| 对象 | 名称 | 状态 |
|---|---|---|
| Compose 项目 | `fusanhe-phase1-test` | 存在（本机） |
| 容器 | `fusanhe-phase1-test-db-1`（mariadb:11.4） | 运行中，healthy |
| 容器 | `fusanhe-phase1-test-espocrm-1`（espocrm:10.0.8-apache，端口 18080） | 运行中，healthy，`FUSANHE_OUTBOUND_PAUSED=true` |
| 卷 | `fusanhe-phase1-test-db-data`、`fusanhe-phase1-test-espocrm-data` | 已创建 |
| 端口 | 18080（HTTP），未占用 8080/8081 | — |

完整清理（确认不再需要演示后）：
```bash
docker compose -p fusanhe-phase1-test --env-file .env.test -f tests/phase1-compose.yaml down -v
```

原 `fusanhe-crm` 项目在核查时确认没有任何运行中的容器/卷，本任务未触碰。

## 9. 隔离与合规确认

- 未推送任何提交（无 remote 操作）；未合并 main；未强推/重写历史/删除分支。
- 未改动原工作目录 `/Users/hanming/Desktop/福三和crm` 的任何文件（含未提交的 `docs/fusanhe-crm.architecture*`）。
- 未访问生产服务器、生产数据库与生产 .env；未读取 ~/.ssh、浏览器凭据或无关目录。
- 未执行真实渠道同步、真实消息发送或真实 AI 付费调用（测试容器 AI_API_KEY 为空，使用确定性 Mock AI）。
- 测试配置使用虚构凭据（`.env.test`，已加入 .gitignore），未提交任何真实凭据。
- Android 客户端未做任何改动。
