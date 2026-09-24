# Web 工作台重构验证计划与证据账本

## 当前证据（实施中，2026-09-24）

| 项目 | 结果与边界 |
| --- | --- |
| 源码架构 | 已检查 `client/custom/src/views/`、`brand.css`、Espo clientDefs、现有前端测试及宪章。17 个自定义 Web 界面由 AMD/原生 Espo 承载；另有原生生成的业务实体页。此项是规划依据，不是重构验收。 |
| shadcn 当前上下文 | 规划前的根目录尚无组件；现已在 `client/custom/ui/` 用官方 CLI 建立 `radix-nova`、React/TypeScript/Tailwind 子工程并安装 16 个组件源文件。客服代表页已实际导入 Button/Table/Badge/Alert/Empty/Skeleton。 |
| Apple HIG 来源 | 已从 Apple 官方结构化文档读取 Accessibility、Layout、Color、Typography、Feedback、Buttons、Search fields、Writing；对应浏览器页面链接列于 `spec.md`。这是指导依据，不代表本项目已符合。 |
| 隔离数据页面观察 | 主任务在 `localhost:18082` 的既有合成测试库观察到：CRM 约 870px 时导航折叠、指标块和大面积空白共存，UI 中英混用；老板页约 870px 时建议表多行挤压、相邻状态数字易混。仅作待改进基线，真实客户导入仍为 0。 |
| 本特性实施与测试 | T001–T007 的技术集成门槛已过：React/shadcn 实际挂载、ACL/停发、同源加载、样式隔离与回退均有运行或测试证据。200% 缩放在当前浏览器不可控制，完整双语和深层角色矩阵须在 T020 验收；其余 Web 页面和 Android 均未完成。 |

## T001 实施前基线（隔离合成环境）

2026-09-24，主任务核对当前 `main` 同源工作树的 Espo clientDefs、Home controller、17 个自定义页面实现与既有前端测试，并在 `localhost:18082` 隔离测试栈观察 CRM、客服和老板页。该栈使用合成数据，固定卷只能由一个工作树挂载；本记录不包含真实客户资料。

| 页面组 | 当前路由/入口 | 回归时必须保留 |
| --- | --- | --- |
| 登录 | `App.loginView` → `fusanhe/login` | Espo 身份验证、错误提示、键盘提交。 |
| 四个首页 | `#Home`、`#Home/crm`、`#Home/service`、`#Home/insights` → Home controller | ACL 模块入口、只读指标与最近列表、老板历史/建议分页及状态、原生实体链接。 |
| 五个列表 | `ExternalConversation`、`AIReplyDraft`、`KnowledgeDocument`、`OutboundTask`、`AutomationAgent` → `fusanhe/list` | 搜索、筛选、排序、分页、行链接与各实体字段。 |
| 会话详情 | `#ExternalConversation/view/{id}` → `external-conversation/record/detail` | 消息时间线、身份确认、草稿审核二次确认、人工接管、销售交接、关系面板。 |
| 三个客户详情 | `Account`、`Contact`、`Lead` → `fusanhe/customer-detail` | 客户概览及原生字段/关系。 |
| 三个上下文详情 | `AIReplyDraft`、`KnowledgeDocument`、`OutboundTask` → `fusanhe/context-detail` | 状态/证据概览及原生字段/关系。 |
| 原生实体页 | Espo 标准列表、详情、编辑、关系、弹层 | 产品/规格、证书、询盘、样品、报价、订单、渠道、身份、消息、审计和 Task 保持可用。 |

基线问题：约 870px 宽 CRM 页有较大空白且静态 UI 中英混用；老板页建议表在同宽度挤压、多行状态计数不易分辨。既有 `client/custom/tests/frontend.test.cjs` 对草稿“保存只 PATCH、拒绝只 PATCH、批准需二次确认、空正文不可批准”、入口 ACL 和部分安全转义有回归断言；实施前运行该文件为 12/12 通过，`make spec-check SPECIFY_FEATURE_DIRECTORY=specs/004-web-workbench-hig` 退出码 0。未在基线阶段宣称其它角色或视口通过。

## 门槛 1：证明确实使用 shadcn/ui 且可与 Espo 共存

### 首轮运行记录（2026-09-24，尚未宣告门槛完成）

- 官方 CLI 已在 `client/custom/ui/` 初始化 `radix-nova` 并安装 16 个组件源文件；生产构建生成同源 AMD 包与作用域 CSS。`npm --prefix client/custom/ui run build`、组件测试 6/6、旧前端加回退测试 15/15 和隔离栈 `app-check` 均通过。当前包约 276 KB 原始 JS、90 KB gzip；CSS 约 60 KB 原始、10 KB gzip。
- 隔离合成栈已切换挂载本工作树，`#Home/service` 浏览器刷新后真实渲染 React/shadcn Table、Button、Badge、Alert、Empty 等组件，读取到 24 条测试会话并正确显示全局停发。首次打包有浏览器 `process is not defined`，修正构建替换后恢复；首次样式受 Espo 默认边框宽度影响，补上作用域内 `border-width: 0` 后恢复正常。以上问题已修，不把失败前的运行算成通过。
- 在 390×844 窄屏，文档宽 379px、视口 390px，没有整体横向溢出；首个表格父容器宽 349px、滚动内容宽 681px，横向滚动局限在表格。`#Home/service → #Home/insights → 浏览器后退` 正常；返回后仅 1 个组件根，旧版回退区保持隐藏。切到原生 Account 列表后，页面结构和控件仍可读，没有观察到组件粗边框污染。
- 尚需在本门槛核实：弹层 portal 与焦点、角色实测/服务端 ACL、CSP、英文 UI 词条完整性、其它代表视口与 200% 缩放。当前隔离账号语言为英语，新页存在静态文案中英混用；该问题交给 D 的 i18n 包，不计为已通过 R09。

### 门槛复核补充（2026-09-24 22:13 CST）

- `make web-check`（包含 `npm ci`、TypeScript、组件 7/7、产物校验、AMD 语法）退出 0；旧 AMD 行为测试 13/13、规格检查、`git diff --check`、隔离栈 `app-check` 和状态接口 PHP lint 均退出 0。状态接口新增角色测试通过：仅有会话读权限者只能看停发状态；渠道读权限者能看脱敏健康字段，Agent 无权限时看不到摘要。
- 874×910 浏览器视口下文档宽 863px，无整体横向溢出；React 根仅一个，控制台最近的 error/warn 为零。JS/CSS 均从 `localhost:18082` 返回 200；页面 CSP 为 `script-src 'self'` 加 nonce/`unsafe-eval` 和 Google Maps 白名单，未见新组件远程资产。Portal 的挂载容器、标题、焦点进入、Escape 关闭和焦点回退已有组件测试，但尚无当前客服页弹层可用于实测。
- 暗色客服页最初的 React 链接计算色为 `rgb(55,105,77)`，页面背景 `rgb(20,24,22)`；A 在 `800e779` 修复 Tailwind cascade layer 与 Espo 全局 `a` 样式冲突，并让新页跟随 Espo 实际主题。完整刷新后原生宿主与新页同为亮色，按钮文字 `rgb(32,37,31)`、普通链接 `rgb(36,91,60)`、背景 `rgb(246,247,245)`；874px 文档宽 863px，控制台 error/warn 为空。原生 Account 页离开时 React 根为 0、列表仍可读。当前浏览器没有提供缩放控制能力，200% 实测延至 T020。
- 首次完整 `tests/test_security_regression.py` 中产品规格审批用例返回 404，原因是原隔离栈未开启 `FUSANHE_FEATURE_PRODUCTS`。随后在同一 `fusanhe-phase1-test` 固定卷上叠加 `tests/phase1-industry-compose.yaml`，rebuild/app-check 通过，受权状态接口确认五个行业模块均为 true；完整安全回归 8/8 通过。该失败不是 Web 改动，复测证据不应与第一次失败混淆。

| 检查 | 通过标准 | 证据位置（实施时填写） |
| --- | --- | --- |
| 官方组件 | `client/custom/ui/components.json`、锁文件、CLI 安装的真实 `src/components/ui/*` 存在；`npx shadcn@latest info --json` 可识别项目与安装组件；代表页渲染 Button/Table/Badge/Alert/Empty/Skeleton 等真实源组件，源码可追到组件导入；按 CLI 文档核对 primitive base 和组件 API | `shadcn info --json`：Vite/TypeScript/Tailwind v4、radix-nova、Radix、Lucide、16 个组件；客服源码及 10 项组件测试。通过。 |
| 构建 | `npm ci`、TypeScript/组件测试、`npm run build` 通过；重复构建产物一致；服务端离线加载本地 JS/CSS，没有 CDN 请求和控制台异常；记录 JS/CSS 的原始与 gzip 大小、首次内容呈现耗时 | `make web-check` 退出 0，生成 JS 276.54 KB / 90.23 KB gzip，CSS 60.10 KB / 10.03 KB gzip；隔离栈资源 200，同源；当前浏览器日志无 error/warn。首次内容呈现耗时未量，留 T020。 |
| AMD 与路由 | `#Home/service` 直接打开、刷新、前进/后退、进入原生实体详情再返回均正常；React root 在离开时卸载，重复进入无双层事件或重复 API 请求，迟到响应不覆写新页面；登录过期时沿用 Espo 的处理 | 390px 与 874px 页面运行、刷新和后退正常；进入 Account 后根数 0，回到客服页根数 1；AMD 迟到回调回退测试通过。登录过期沿用宿主，最终验收再做人工抽查。 |
| CSS/portal 隔离 | 代表页运行前后在原生 Account/Lead/产品表单测量关键 computed styles；无 Tailwind Preflight 污染；Dialog/Sheet 标题、焦点、Escape、portal 样式在本地根内；暗色、高对比、缩放下弹层可读 | Account 原生列表视觉和根卸载通过；CSS 生成脚本拒绝非作用域选择器；Portal 焦点/Escape/回退组件测试通过。深层原生表单、高对比和 200% 仍属 T020，不计已通过。 |
| 权限/停发 | read-all、本人范围、无读取权限、无草稿批准权限的合成账号逐一检查；UI 不显示不可读数据，直接 URL 仍由服务端阻断；状态接口失败时明确“未知”，不能默认“已停发” | 受限角色状态接口测试通过；客服页面显示停发开启；前端无权限不请求受限范围与未知停发组件测试通过，旧回退页缺字段显示“状态未知”。完整多角色浏览器路径留 T020。 |

**阶段 1 开始判定**：AMD/shadcn 共存、权限边界、停发和已知 CSS 缺陷均通过复核；200% 与完整角色/语言/原生实体矩阵是仍待 T020 验收的明确缺口，不能据此宣称 Web 全部完成。若后续发现关键 ACL、停发或 CSS 污染回归，立即停下迁移并恢复旧页面。

## 门槛 2：Web 全页面功能回归

| 界面/页面组 | 必查行为与状态 | 角色 |
| --- | --- | --- |
| 登录与全局壳层 | 标题/Logo/版权、输入标签、密码错误、键盘提交、登录后导航、当前页状态、账户菜单、窄屏侧栏、退出 | 匿名、普通用户 |
| `#Home`、CRM、客服 | 模块入口 ACL、指标未知值、最近记录与待办链接、刷新、空态、局部失败、双语与停发提示 | 老板、销售、客服、受限用户 |
| `#Home/insights` | 覆盖率“待对账”、查询/状态筛选/分页、建议排序、证据链接、分析完成/失败/过期/未分析、无权限、870px 密集表；数据仅用合成库 | 老板、本人范围、无读取权限 |
| 五类自定义列表 | 各自列与时间、搜索、筛选、排序、分页、清除、行点击/Enter、内层链接不触发行跳转、空/错/加载、过长文本不遮挡操作 | 有权/无权 |
| 会话详情 | 时间线、来源/译文、身份候选与人工关联、草稿生成/保存/拒绝/批准、接管/恢复、销售跟进、失败任务、引用资料、原生关系面板；页面转窄时审核信息仍可见 | 客服、销售、审核人、受限用户 |
| Account/Contact/Lead 与三种上下文详情 | 字段与关系区不丢；缺失值、客户阶段、身份待确认和风险准确；只读用户无编辑动作；引用回会话 | 销售、审核人、受限用户 |
| Espo 原生业务实体页 | 产品/规格、证书、询盘、样品、报价/明细、订单/明细/发货、渠道、身份、消息、审计、Task 的列表/详情/编辑/关系与弹层都可读、可键盘操作、无 CSS 失真；业务操作仍由原生表单/服务端处理 | 对应有权用户、只读用户 |
| Dashlet/结构化字段 | 首页 dashlet 到老板页链接、JSON 字段只读可理解显示、无敏感原文被误翻译 | 有权用户 |

关键变更只在隔离合成库验证；不得使用 8080 主演示库试写。浏览器人工审核可点击“批准”前的确认步骤；最终提交行为用合成隔离数据或 API mock 验证，且保持全局停发。验证后检查隔离库任务/记录变化是否符合预期，不允许双提交或实际外发。

## 门槛 3：可访问性、语言和视觉矩阵

| 维度 | 检查方法与通过标准 | 证据位置（实施时填写） |
| --- | --- | --- |
| 视口与缩放 | 1920×1080、1440×900、1280×720、1024×768、768×900、390×844，每种至少覆盖客服代表页、会话详情、老板页与原生编辑页；200% 浏览器缩放仍可访问导航/主要动作，页面无非预期整体横向滚动，表格仅区域内滚动 | 待填 |
| 键盘与焦点 | 只用键盘完成主要导航、筛选、列表打开/返回、弹层开启/关闭及批准确认前流程；顺序与视觉一致，焦点持续可见，关闭弹层回到触发器；避免仅绑定 `tr` 而无明确可访问行内动作 | 待填 |
| 屏读/语义 | 页面主标题唯一、表格列/行关联、表单标签、错误关联、Dialog/Sheet Title、`aria-live` 不刷屏；用 Axe 或等效自动扫描加人工读屏抽查，严重/关键违规 0 | 待填 |
| 色彩/文字 | 正文至少 4.5:1，重要界面边界与大字至少 3:1；亮色、暗色、高对比/forced-colors 各检查一遍；颜色之外有状态词，200% 缩放下标签不截断关键操作 | 待填 |
| 动画/触控 | `prefers-reduced-motion` 下没有不必要循环动画；粗指针模式实际目标至少 44×44 CSS px 且不重叠；按压/禁用/处理中状态可见 | 待填 |
| 中英 | 中文与英文各走一次 17 个自定义页面代表流程；不能出现同页混用的静态 UI 文案，系统状态与按钮一致；客户原文/草稿正文原样保留，日期含上海时区语义 | 待填 |
| 视觉 | 每页看导航、任务优先级、对齐、表格扫描、空态密度、弹层比例、证据与推断层级、截断提示；重点复查 870px 老板建议表与 CRM 空白区。截图仅限合成库并放在 Git 忽略的本地产物目录；文档只写路径/摘要，不提交业务内容 | 待填 |

## 建议执行命令（由独立验收 Agent 核对实际输出）

在隔离 worktree 中，先停旧测试栈再以**同一个** `fusanhe-phase1-test` 项目和固定卷启动，避免两个项目共用卷；不要动 8080 主演示库。

```sh
make spec-check SPECIFY_FEATURE_DIRECTORY=specs/004-web-workbench-hig
make verify-offline
npm ci --prefix client/custom/ui
npm --prefix client/custom/ui run build
npm --prefix client/custom/ui test
node --test client/custom/tests/frontend.test.cjs
find client/custom/src -name '*.js' -print0 | xargs -0 -n1 node --check
git diff --check
```

PHP/运行检查在隔离项目中显式执行，例如 `docker compose -p fusanhe-phase1-test --env-file .env.test -f tests/phase1-compose.yaml exec -T espocrm bin/command app-check`、`bin/command rebuild` 和自定义 PHP lint；实际容器名、测试环境变量以当时项目配置为准。运行与截图均需记录命令、退出码、角色、视口、时间及关键结论，不打印密钥/客户原文。涉及更改审批链或权限时，重跑 `client/custom/tests/frontend.test.cjs`、`tests/test_phase1.py`、`tests/test_security_regression.py`、`tests/test_boss_insights_runtime.py` 的适用部分。

## 完成判定与回退验证

独立验收 Agent 逐条填写 R01–R13 的“通过/失败/阻塞”、证据路径和复现；主任务修复后再次复验。任何权限泄漏、自动发送、审批绕过、停发状态误报、客户原文误译、全局 CSS 污染或原生业务表单不可用，均阻断 Web 完成。Android 和真实 Alibaba 回填保持独立未完成。

回退演练：移除 React 入口引用后旧 AMD 界面恢复，刷新浏览器无旧 bundle 混用，原生导航和记录详情仍可打开；不涉及数据库回滚。若完整部署更换静态资产，部署前保存原版本与 Espo 配置并验证能切回；不得以“代码可 revert”代替实际回退试验。
