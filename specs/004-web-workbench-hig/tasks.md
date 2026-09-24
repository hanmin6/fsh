# Web 工作台重构任务与 Agent 文件所有权

所有任务初始为未完成。`[P]` 表示技术门槛通过后可并行；同一工作树并行时只按下表的所有权写文件。任何 Agent 发现要改其他包文件，先向主任务说明接口需求，由文件所有者修改，避免覆盖。规划 Agent 只编写本规格目录，独立验收 Agent 不承担功能实现。

| 包 | Agent 与独占写入区域 | 依赖与交付 |
| --- | --- | --- |
| A 基础设施 | `client/custom/ui/{package.json,package-lock.json,components.json,vite.config.*,src/components/**,src/lib/**,src/entry.tsx,src/styles.css}`、`client/custom/src/fusanhe/ui-runtime.js`、`client/custom/src/views/fusanhe/react-host.js`、`client/custom/res/fusanhe/{ui.css,brand.css}`、`custom/Espo/Custom/Resources/metadata/app/client.json`、`Makefile` | 先完成。提供稳定 `mount/update/unmount`、host 类型、组件库、token 与 CSS 隔离；其它 Agent 不并发运行 shadcn add 或改锁文件。 |
| B 首页与老板页 | `client/custom/src/controllers/home.js`、`client/custom/src/views/fusanhe/{home,crm-home,service-home,insights}.js`、`client/custom/ui/src/screens/dashboard/**`、`client/custom/ui/src/screens/insights/**`、包内测试 | 先用 `#Home/service` 做代表页，通过门槛后迁移其他页。不得改 A 的入口和全局 CSS。 |
| C 列表与会话 | `client/custom/src/views/fusanhe/list.js`、`client/custom/src/views/external-conversation/record/detail.js`、`client/custom/ui/src/screens/queue/**`、`client/custom/ui/src/screens/conversation/**`、包内测试 | 门槛通过后并行。保留所有读/写操作与服务器保护；通过 A 提供的 host API。 |
| D 登录、客户与原生页 | `client/custom/src/views/fusanhe/{login,customer-detail,context-detail}.js`、`client/custom/src/views/{dashlets/fusanhe-operations,fields/structured}.js`、`client/custom/ui/src/screens/customer/**`、`client/custom/res/fusanhe/native.css`、`custom/Espo/Custom/Resources/i18n/{zh_CN,en_US}/Fusanhe.json`、包内测试 | 门槛通过后并行。A 预先在 `client.json` 引入 `native.css`；D 不改 `brand.css`。 |
| 主任务/验收 | `specs/004-web-workbench-hig/verification.md`、必要的跨包测试、交接文档 | 主任务处理包接口与集成；**最后一位独立 Agent** 根据矩阵验收，退回缺陷后由对应包修复并复验。 |

共同接口由 A 在 `client/custom/ui/src/entry.tsx` 预设 B/C/D 的页面注册占位；A 可在移交前创建最小占位模块，随后文件所有权交给对应包，A 不再修改。包内各自导出屏幕工厂和类型。A 冻结接口之前不要创建冲突的注册文件。所有包使用已安装的组件；若缺组件，由 A 先运行 CLI、审阅源码并提交锁文件变化。并行阶段 B/C/D 只运行不改产物的类型检查/组件测试；最终静态 bundle 由主任务在合并后单次构建，避免并发写入 A 拥有的生成文件。现有 `client/custom/src/views/fusanhe/common.js` 由 A 只读对照，除非主任务指定单一所有者，否则没有 Agent 修改它；新 UI 的状态与翻译通过 host/React 层实现。

## 阶段 0：运行基线与技术门槛（顺序）

- [ ] T001 [US01] 主任务记录 17 个自定义 Web 界面、原生实体页路由、现有角色和关键操作的基线矩阵与隔离栈截图；仅写脱敏结论到 `specs/004-web-workbench-hig/verification.md`，不保存真实客户内容。
- [ ] T002 [US04] A 在 `client/custom/ui/` 建立 React + TypeScript + Vite + Tailwind 独立项目，使用官方 `shadcn` CLI 初始化配置并安装规范所需组件；确认 `components.json`、primitive base、图标库和 `npm ci` 可重现，并将 `npx shadcn@latest info --json` 结果报告给主任务记录。
- [ ] T003 [US04] A 实现 `client/custom/ui/src/entry.tsx` 与生成的 `client/custom/src/fusanhe/ui-runtime.js`，提供 AMD 可加载的 `mount/update/unmount` 和 Espo `Ajax/ACL/Router/i18n/notification` host 接口；`client/custom/src/views/fusanhe/react-host.js` 的 `remove` 释放 React 根及异步回调。
- [ ] T004 [US03] A 在 `client/custom/ui/src/styles.css`、`client/custom/res/fusanhe/ui.css`、`client/custom/res/fusanhe/brand.css` 建立亮/暗/高对比语义 token、字号、间距、状态及焦点规则；CSS 不包含影响全站的 Tailwind Preflight，组件样式不污染原生 Espo 页，portal 层焦点和样式在根内；`client.json` 按确定顺序引用 CSS 并预留 D 的 `native.css`。
- [ ] T005 [US04] A 为 `client/custom/ui/package.json` 增加可复现构建/产物漂移/组件测试脚本，并在 `Makefile` 连接 Web 检查；构建只输出本地静态资产，组件源码和构建产物都受版本控制。
- [ ] T006 [US01] B 仅迁移 `#Home/service`：在 `client/custom/src/views/fusanhe/service-home.js` 与 `client/custom/ui/src/screens/dashboard/service.tsx` 使用实际 shadcn Table/Button/Badge/Alert/Empty/Skeleton，保留 ACL、计数未知值、停发状态与各实体链接，并建立只读操作回归测试。
- [ ] T007 [US04] 主任务在隔离栈对 T002–T006 做门槛验收：AMD 加载、控制台/网络错误、路由进出/刷新/后退、卸载、不同角色、CSP、portal、原生页 CSS 对照、键盘/200%/870px 与 390px、停发状态读取。结果写入 `specs/004-web-workbench-hig/verification.md`；门槛不通过时保持旧 UI 可回退，不启动并行迁移。

## 阶段 1：按独占文件包并行迁移（依赖 T007 通过）

- [ ] T008 [P] [US01] B 用 `client/custom/ui/src/screens/dashboard/home.tsx` 与 `client/custom/src/views/fusanhe/home.js` 重构模块入口，按 ACL 显示 CRM/客服入口、最近业务与明确空态；保持原 `#Home` 路由和页面标题。
- [ ] T009 [P] [US01] B 用 `client/custom/ui/src/screens/dashboard/crm.tsx` 与 `client/custom/src/views/fusanhe/crm-home.js` 重构 CRM 工作台，减少大面积空白，区分总量/待办/最近客户；保留历史客户入口与原生实体链接。
- [ ] T010 [P] [US01] B 用 `client/custom/ui/src/screens/insights/**` 与 `client/custom/src/views/fusanhe/insights.js` 重构老板页的覆盖率、今日建议、筛选分页、分析和证据检查；870px 下多行建议表可读、状态计数不粘连，未知覆盖率不显示为零，合成数据标注只在测试文档中。
- [ ] T011 [P] [US03] B 为 `client/custom/ui/src/screens/dashboard/**` 和 `insights/**` 增加中英文 UI 字典与状态、空/错/旧数据、窄屏及键盘组件测试；业务原文不自动翻译。
- [ ] T012 [P] [US01] C 在 `client/custom/src/views/fusanhe/list.js` 与 `client/custom/ui/src/screens/queue/**` 保留五类列表的搜索/渠道/负责人/国家/状态/SLA/未读/排序/分页，实际使用 shadcn Table、Field、Select、Badge、Empty；整行键盘动作与行内链接不冲突。
- [ ] T013 [P] [US02] C 在 `client/custom/src/views/external-conversation/record/detail.js` 与 `client/custom/ui/src/screens/conversation/**` 重构会话三栏和窄屏分区，保留时间线原文/译文/附件说明、身份确认、引用证据、人工接管和原生关系面板；用 Dialog/AlertDialog 等真实组件实现高风险确认。
- [ ] T014 [P] [US02] C 为 `client/custom/ui/src/screens/conversation/**` 增加权限与状态测试：保存仅保存、拒绝仅拒绝、批准须人工审核确认、无权限按钮不可操作、重复/迟到响应无额外提交、全局停发未知文案正确；结合现有 `client/custom/tests/frontend.test.cjs` 行为契约。
- [ ] T015 [P] [US03] D 以 `client/custom/src/views/fusanhe/login.js` 与 `client/custom/res/fusanhe/native.css` 整理登录和 Espo 全局导航/弹层/原生列表/表单/关系区外观；测试现有登录输入、错误、品牌与版权、主题切换与触控目标，不能重写认证。
- [ ] T016 [P] [US02] D 在 `client/custom/src/views/fusanhe/{customer-detail,context-detail}.js`、`client/custom/ui/src/screens/customer/**` 迁移客户/联系人/线索与草稿/知识/发送任务的业务概览；保留原生详情字段/关系面板，明确缺失字段和高风险事实待确认。
- [ ] T017 [P] [US03] D 在 `client/custom/src/views/{dashlets/fusanhe-operations,fields/structured}.js`、`client/custom/res/fusanhe/native.css` 与 `custom/Espo/Custom/Resources/i18n/{zh_CN,en_US}/Fusanhe.json` 完成 dashlet/结构化字段/双语状态的一致性，避免通过 DOM 文本遍历误译客户原文。
- [ ] T018 [P] [US03] D 对产品、规格、证书、询盘、样品、报价/明细、订单/明细/发货、渠道、身份、消息、审计和 Task 等 Espo 原生列表/详情/编辑/关系页逐类运行视觉和键盘检查；将发现的共性修复只写入 `client/custom/res/fusanhe/native.css` 和 D 拥有的扩展文件。

## 阶段 2：集成与独立验收（顺序）

- [ ] T019 [US04] 主任务合并 B/C/D 后在 `specs/004-web-workbench-hig/verification.md` 对照 R01–R13 和源码/产物清单，运行前端构建、组件/AMD 测试、旧契约/安全回归、Espo rebuild/app-check；有跨包缺陷指定唯一文件所有者修复。
- [ ] T020 [US03] **独立验收 Agent** 按 `specs/004-web-workbench-hig/verification.md` 用隔离合成数据对 17 个自定义界面和原生实体矩阵做多角色、双语、六视口、200% 缩放、键盘/屏读标签、暗色/高对比、局部状态与关键业务路径验收，记录截图位置、失败复现和未覆盖项；不把代码完成视为验收完成。
- [ ] T021 [US04] 主任务按 T020 缺陷派回 B/C/D/A 的独占文件，修复后请同一独立 Agent 复验；在 `specs/004-web-workbench-hig/verification.md` 标明通过/失败/阻塞及实际证据。
- [ ] T022 [US04] 主任务更新 Web 开发交接与发布/回退说明，核对构建产物、依赖许可证、Git 无密钥/客户内容，确保未把 Android 或真实 Alibaba 回填误标为已完成；交接入口写入 `README.md` 或相应 `docs/` 文档。

## 依赖图与阻断条件

`T001 → T002/T003/T004/T005 → T006 → T007 → {T008–T018 并行} → T019 → T020 → T021 → T022`。T003 依赖 T002；T004 的最终 CSS 构建依赖 T002；T006 依赖 A 提供的稳定接口与最小组件。任何 T007 失败都停在旧界面并保留失败证据。任何关键 ACL、批准、停发或消息原文回归失败都阻断 Web 完成，即使截图视觉通过。
