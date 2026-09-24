# Web 工作台重构实施计划

## 架构决定

保留 EspoCRM 10.0.8 作为 Web 宿主和系统记录层。它继续拥有会话认证、ACL、`#Home/*` 与实体路由、全局导航、原生 CRUD/关系面板、API、业务状态机。新增 **独立 React/TypeScript/Tailwind 源工程**，通过官方 shadcn CLI 安装真实组件源；预编译成同源静态文件，并由轻量 AMD 宿主视图按需挂载到自定义页面的内容区域。生产 Web 不需要 npm 服务或远端 CDN，也不把整个 EspoCRM 迁到 React。原生生成页沿用 Espo 扩展点和共享语义 token 进行完整视觉与可访问性适配。

这是一项需要实际验证的技术方案，不是现成能力。首次实施只做 `#Home/service` 的只读代表页，证明 React、shadcn 组件、Tailwind CSS、Espo 路由与原生实体详情共存；再扩展其他页面。若失败，撤回试验性静态文件和入口，保留旧 AMD 页面并报告具体失败条件。不能把视觉仿制算作 R11 通过。

### 计划目录与运行契约

| 路径/契约 | 所有者与作用 |
| --- | --- |
| `client/custom/ui/`（新增） | 独立 Vite React TypeScript 项目；`components.json`、`package.json`、锁文件、shadcn CLI 安装的 `src/components/ui/*`、`src/lib/utils.ts`、测试与设计 token 源。选定一种 primitive base（优先 Radix，理由是 portal 容器可控）；`npx shadcn@latest info --json` 必须确认最终项目上下文，组件使用前执行 `docs`/`search`/`view`。不从 GitHub 原样复制组件文件。 |
| `client/custom/ui/src/entry.tsx` | 单一显式导出 `mount(target, screen, host, props)`、`update`/`unmount`；注册页面包。运行时根节点存在于 `data-fsh-ui-root` 内，React 在卸载时释放订阅和请求序号。 |
| `client/custom/src/fusanhe/ui-runtime.js`（生成） | Vite library/IIFE 构建后用可复现脚本封装为命名 AMD 模块；仅在自定义视图加载。包含 React runtime，不依赖外网脚本。构建文件禁止手工编辑。 |
| `client/custom/res/fusanhe/ui.css`（生成） | shadcn/Tailwind 样式与变量；组件作用域限制在 `data-fsh-ui-root`，不启用全局 Preflight，隔离 utility class 与 Espo 原生 `.btn/.table/.panel` 等。弹层 portal 节点保留在该根中，避免主题和焦点逃逸。若具体 primitive 无法设置 portal 容器，须通过实测调整实现，不能悄悄放任全局污染。 |
| `client/custom/src/views/fusanhe/react-host.js`（新增） | AMD 适配器：`afterRender` 挂载、`remove` 先卸载、页面标题、路由状态、迟到响应防护。注入 Espo `ajax`、`getAcl`、`getLanguage`、`getRouter`、UI 通知和模型。不能把 admin token、Cookie 或服务器权限复制到 React 状态。 |
| `client/custom/res/fusanhe/brand.css` 和 `metadata/app/client.json` | 原生 Espo 壳层、登录、菜单、表单、关系面板与新 CSS 的顺序/作用域。原生业务页须随 token 同步，不新增第二侧栏。 |

构建产物与源代码一起提交，锁定依赖并由 `npm ci && npm run build` 重建校验；CI/本地检查发现产物漂移即失败。Node 构建只在开发/发布阶段，Espo 容器仍只载入本地静态资源。选用源工程自己的 npm runner，因为仓库根没有 `packageManager`，初始化后锁文件决定 runner。正式发布前用包审计与许可证清单确认依赖，无远程字体/图标加载。

`host` 最小接口：`api.get/post/patch` 调用现有 Espo Ajax、`can(scope, action)` 用现有 ACL、`navigate(hash)` 用 Espo Router、`language.translate(key)` 用 Espo i18n、`notify(...)` 用 Espo UI、`currentUserId`、`getOutboundState()` 从现有只读状态接口读取。组件只负责显示和发出明确用户动作；服务端继续裁决授权、数据范围与状态。不得通过全局 `fetch` 绕过宿主封装，也不得把敏感资料写入浏览器日志、持久缓存或截图。React 文本默认转义；禁用 `dangerouslySetInnerHTML` 处理业务数据。

### 设计 token 与组件结构

组件只用语义 token 和内置 variant；`className` 主要用于布局，不用散落的十六进制色覆写组件。起始 token **建议值，需在代表页用对比度检查后冻结**：

| 语义 | 亮色起点 | 暗色起点 | 约束 |
| --- | --- | --- | --- |
| `background` / `foreground` | `#F6F7F5` / `#20251F` | `#141816` / `#F4F6F3` | 内容层清楚、背景不抢任务 |
| `card` / `muted` / `border` | `#FFFFFF` / `#EFF2EF` / `#D8DED8` | `#1C231E` / `#273029` / `#3D4940` | 表格与分区优先用细边框，浮层外少阴影 |
| `primary` / `primary-foreground` | `#AA3022` / `#FFFFFF` | `#F07865` / `#141816` | 品牌红用于主要动作；必须实测 hover/disabled 对比 |
| `sidebar` / `sidebar-foreground` | `#20251F` / `#FFFFFF` | `#141816` / `#F4F6F3` | 沿用一套 Espo 导航、选中态含文字 |
| `destructive` / `warning` / `success` | 独立语义变量 | 独立语义变量 | 状态同时有文字/图形，不只靠红绿 |
| `ring` / `input` / `radius` | 明显焦点环 / 中性边线 / `6px` | 对应高对比值 | 以 `rem` 定义文字和间距 |

基础排版：正文约 14px、表格 13–14px、辅助信息不小于 12px，页面标题约 20px；4px 间距基数，普通视觉控件 34–38px、实际触控目标 44×44 CSS px，表格行约 44px。控件视觉密度不能以隐藏标签或缩小点击区域换取。`prefers-color-scheme` 和 `prefers-contrast`/`forced-colors` 使用语义 token；减少动态效果。布局模型是 Espo 单侧栏 + 页面工具栏 + 表格/队列 + 有明确上下文时才出现检查器；老板页保持覆盖率事实、规则建议、历史列表和证据检查的顺序。窄屏将检查器转为具标题的 Sheet/分区，表格允许容器内滚动或按列优先级收敛，不能将敏感关键字段静默丢弃。

共用 shadcn 组件：Button、Table、Badge、Alert、Input、Field、Select、Tabs、Dialog/AlertDialog、Sheet、Empty、Skeleton、Separator、Tooltip，必要时 Pagination；不要引入一套新的 Sidebar 与 Espo 导航竞争。字段组合、Select/Dropdown Group、弹层标题、Spinner 加 disabled、状态 Badge、空态 Empty、提示 Alert 依照已读技能规则。登录和原生编辑表单若仍由 Espo 渲染，明确记录为原生适配，不宣称它们渲染了 shadcn React 组件。

### 渐进迁移顺序与隔离

1. **技术门槛**：仅安装/构建组件并挂载代表性只读 `#Home/service`；一进一出路由、刷新、登录过期、不同角色、弹层 portal、CSS 污染、Axe/键盘、窄屏和生产 CSP 均需实际验证。此门槛未过，不并行改写全部页面。
2. **并行页面包**：A 的组件/API/样式契约冻结后，B 迁移 Home/CRM/客服/老板只读工作台，C 迁移五类列表与会话详情，D 迁移登录、客户/上下文详情、dashlet/字段及原生实体视觉。各包只修改自己的文件；新增共用组件由 A 集中合并，避免并发改 `components.json`、锁文件、入口和 `brand.css`。
3. **整体验收**：独立验收 Agent 依据 `verification.md` 对真实运行的各角色、各视口和关键操作做检查，记录阻断缺陷及证据；实现 Agent 修复后由验收 Agent 复核。只有 Web 通过后，才单独定义 Android 的 shadcn 不适用的原生设计系统计划。

### 兼容与安全边界

- 现有 `#Home` 四路径、五类实体列表、客户/会话/上下文记录路由、ACL、服务端响应字段均保持；原生表单、关系面板、全局搜索和账户菜单不重新实现。页面模块装载失败应有可见错误与刷新/回退路径，不能显示空白页。
- 来源“待对账”、分析“待处理/失败/过期”、身份“待确认”、真实/模拟、未知停发状态均有明确词语，不能在 UI 计算时把 `null` 转成 `0`。老板页的合成数据只能在隔离测试栈展示，任何截图/日志不得含真实客户资料。
- 业务写操作仍调用现有 endpoints，批准/人工接管/身份关联/转销售的按钮权限与二次确认由既有服务端规则保护。React 状态不得使按钮误认已审批、已发送或可重复提交。无权限用户直接导航时由服务端拒绝，前端只能作额外可用性门控。
- 不改变 `FUSANHE_OUTBOUND_PAUSED` 或外发执行端。不新增自动外发、定时触发、数据库迁移。若状态接口失败，显示“未知”并要求审核者核查。
- 根级 `brand.css` 与组件 CSS 的影响范围分开，用浏览器 computed style 检查未迁移的 Espo 原生页和登录页在挂载前后的差异；除计划的 token 变化外不允许意外 reset。

## 测试与发布路径

开发期先做静态与单元/组件测试，再用隔离合成栈做运行和截图。隔离栈位于 `http://localhost:18082`；`tests/phase1-compose.yaml` 使用固定卷名，同一时间只运行一个测试项目，换 worktree 时由主任务协调停旧栈再启新栈。不要修改 `localhost:8080` 主演示库。数据由原有隔离测试生成，不把真实客户记录、Cookie 或凭证放入 repo 和截图。计划新增 `npm ci`、`npm run build`、前端单元/组件测试、`node --check` AMD 包装、`make spec-check SPECIFY_FEATURE_DIRECTORY=specs/004-web-workbench-hig`、`make verify-offline`、`make check`、既有前端和关键后端安全回归；浏览器跑完整路由/角色/视口矩阵及 Axe/键盘/对比度检查。状态详见 `verification.md`。

回退通过撤下新 `ui-runtime.js`/`ui.css` 与 React host 的入口引用，恢复原 AMD 视图和 `brand.css`；没有 schema 迁移。部署前备份当前静态资产与 Espo 设置，切换版本后完整刷新以免旧 AMD 模块滞留。若只读代表页门槛失败，停止扩展并维持原页面；记载失败与可重试条件。

## 宪章检查

本目录在行为变更前建立；Web UI 不能绕过服务端 ACL 与状态机；人工批准/全局停发保持；无真实客户/密钥进入 Git、测试和 AI；验收必须含运行证据；静态构建与 CSS 可回退。对应《福三和 CRM Constitution》I–V；无拟议例外。
