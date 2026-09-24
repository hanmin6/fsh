# Web 工作台视觉与交互重构规格

## 背景、目标和边界

用户要求以 [`shadcn-ui/ui`](https://github.com/shadcn-ui/ui) 提供的 `shadcn` 技能和 [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/) 为依据，彻底重构项目前端；先完成 Web 工作台，后续再处理 Android。Web 用户包括老板、销售、客服、审核人和管理员。他们最常做的事是从队列定位会话或客户、核实身份与资料、审阅回复草稿、查看跟进建议、处理失败任务。误点批准、混淆真实与模拟、把未知停发状态显示成安全、权限外数据进入页面，均属于高风险缺陷。

本特性覆盖当前 Web 可见体验：17 个自定义界面、共享导航与登录、运营 dashlet、结构化字段，以及 EspoCRM 原生生成的实体列表/详情/编辑/关系/弹层在统一主题下的可用性。17 个自定义界面为：登录 1；`#Home`、`#Home/crm`、`#Home/service`、`#Home/insights` 4；由 `client/custom/src/views/fusanhe/list.js` 服务的统一询盘、草稿队列、知识文档、发送任务、执行端列表 5；会话详情 1；Account/Contact/Lead 客户详情 3；AIReplyDraft/KnowledgeDocument/OutboundTask 上下文详情 3。原生生成页不是这 17 个的组成部分，但同样必须进入 Web 验收矩阵。

本特性不改 Android（现有 12 个独立页面和 2 个会话弹层）、业务 API/数据模型、真实 Alibaba 回填、AI 提示词或发送策略。Android 重构是 Web 验收后的独立特性，不能用本特性完成状态代替。若实现发现需要改变 API，必须先补充契约、权限和单独任务。

## 已确认的现状

- Web 由 EspoCRM 10.0.8 的 AMD `define(...)` 视图、原生 Backbone/jQuery 记录页和 `brand.css` 组成。仓库根目录没有 `package.json`、`components.json`、React、Vite 或 Tailwind。`npx shadcn@latest info --json` 报告 `framework=Manual`、`config=null`、`components=[]`。目前不能称任何现有界面已使用 shadcn/ui 组件。
- 页面入口由 `custom/Espo/Custom/Resources/metadata/clientDefs/{App,Home,ExternalConversation,...}.json` 和 `client/custom/src/controllers/home.js` 提供；`metadata/app/client.json` 注入 `client/custom/res/fusanhe/brand.css`。会话详情有人工接管、身份确认、草稿保存/拒绝/批准、跟进任务等状态和操作；`Home/insights` 是只读老板历史页。
- 读取受 Espo ACL 和服务端权限控制，客户端仍要根据 `getAcl().checkScope(...)` 控制可见入口。`GET /Fusanhe/status` 提供全局停发状态，失败时必须显示“未知”。批准草稿创建发送任务的现有二次确认和人工审核勾选不能减少。
- 既有桌面体验已采用紧凑表格，但存在页面间字级、空态、操作反馈和响应式差异；部分界面在同一语种下混用中英文。原生记录页必须保留关系面板与已有业务表单。

## 用户故事与可验收要求

### US01：在统一工作台中找到下一项工作

- R01：导航结构、页面标题、返回路径与当前位置在所有 Web 页面保持一致。`#Home/*` 与实体路由仍可直接打开、刷新、使用浏览器后退/前进；不能出现第二套冲突的侧栏或失效链接。
- R02：CRM、客服、老板页以具体待办与列表为主，统计保持紧凑。表格支持清楚的列标题、筛选状态、分页/更多、行内动作；信息密集但不通过巨大空白卡片或装饰图填充。现有搜索、排序、筛选和链接结果不变。
- R03：所有加载、空、无权限、错误、旧数据/未知、成功与处理中状态可辨认且有下一步。失败的局部请求不让整个工作台误报为零；老板页“来源待对账”和“分析失败”不得伪装成完整数据。

### US02：安全地审阅会话与草稿

- R04：会话的时间线、原文/译文、身份、资料引用、风险、负责人、草稿与人工操作在桌面可同时扫描；窄屏按任务顺序切换或折叠，不能隐藏关键审核信息。原生记录详情和关系区域继续可用。
- R05：保存、拒绝、生成、批准、接管、身份关联、转销售的语义与权限保持原样。批准仍需明确复核与确认，任何 UI 重构都不自动发送；停发状态未知时不能宣称发送安全。错误反馈靠近相关操作并允许重试。
- R06：客户、联系人、线索、上下文详情及原生业务实体页显示相同的状态用语、证据与缺失值规则；未经核实的客户身份、产品/报价/证书等不得被 UI 包装成已确认事实。

### US03：不同环境和能力的用户都能使用

- R07：首批明确支持 1920×1080、1440×900、1280×720、1024×768、768×900、390×844 的视口，以及 200% 浏览器缩放。导航、主要动作和内容不被遮盖；长表格可在自身区域横向滚动，页面整体没有无意的横向滚动。触控输入采用至少 44×44 CSS px 的可点击区域或等效无重叠区域；视觉控件可以保持紧凑。
- R08：键盘能按可预测顺序访问链接、筛选、表格动作、弹层及确认流程；焦点可见，弹层有标题、进入后焦点落入、关闭后返回触发点，Escape 和表单标签正确。状态不能只靠颜色区分；正文普通文字对比度至少 4.5:1，大字/图标及必要界面边界至少 3:1（本项目采用 WCAG 2.2 AA 的 Web 验收值）。尊重 `prefers-reduced-motion`，不以持续动画表达唯一状态。
- R09：简体中文和英文 UI 文案在各自语言设置下完整、一致，操作词、状态与错误一致；客户原文、草稿正文和其他业务内容不被自动翻译。时间与日期明确时区，老板建议维持上海当日语义。
- R10：轻色、暗色和高对比偏好均需有可读的语义色映射；浏览器缩放和系统文字放大时，内容不裁切、按钮不只剩图标。不存在未经验证的“暗色主题已支持”声明。

### US04：可维护地使用 shadcn/ui

- R11：新建隔离的 React/TypeScript/Tailwind 构建层，在其中通过官方 `shadcn` CLI 安装并提交实际组件源文件（至少 Button、Table、Badge、Alert、Input/Field、Dialog 或 AlertDialog、Empty、Skeleton）。自定义 Web 工作台必须真正渲染这些组件；不能只复制色彩/圆角然后声称使用 shadcn/ui。组件版本、项目配置、依赖锁文件及离线部署产物可复现。
- R12：React 只负责渐进迁移的自定义内容区域，通过受控桥接使用 Espo Ajax、ACL、路由、语言与通知；EspoCRM 仍是身份、原生导航、记录 CRUD、关系面板与业务状态机的所有者。组件样式不得污染未迁移的 Espo 原生页面；路由离开时卸载、取消/忽略迟到响应，避免重复事件与内存泄漏。
- R13：代表性页面通过运行时和视觉验收后，才扩展到剩余页面。若官方组件与 AMD/CSS/弹层机制不能可靠共存，保持原页面可回退，记录阻碍，不把仅按技能原则做的原生适配称为 shadcn/ui 已接入。

## 设计和外部规范的解释

Apple HIG 面向 Apple 平台；本项目在 Web 采用其可转译的原则，不把 iOS 原生控件、Liquid Glass 或 SwiftUI 当作 Web 实现要求。验收解释如下：

| Apple 官方依据 | 本项目的可核验解释 |
| --- | --- |
| [Layout](https://developer.apple.com/design/human-interface-guidelines/layout)：按重要性与阅读顺序安排内容、对齐帮助扫描、布局适应尺寸 | 主任务先于次要统计；列表与检查器关系清楚；上述视口与缩放验收 |
| [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)：文字可放大、足够对比、颜色不是唯一线索、键盘访问、减少动态效果 | R07–R10；用真实键盘与自动化可访问性检查验收 |
| [Color](https://developer.apple.com/design/human-interface-guidelines/color)：语义色、亮暗与高对比情境、颜色以外的状态提示 | 状态文字/形状配合语义 token，亮暗/高对比快照和对比计算 |
| [Typography](https://developer.apple.com/design/human-interface-guidelines/typography)：可读性与层次 | 相对单位与受限字级，200% 缩放仍可读；表格关键字段不因省空间消失 |
| [Feedback](https://developer.apple.com/design/human-interface-guidelines/feedback)：反馈与影响程度匹配、靠近上下文、重大操作确认 | 局部加载与局部错误、审核确认、提交后状态反馈 |
| [Buttons](https://developer.apple.com/design/human-interface-guidelines/buttons)：明确动作名、按压反馈、足够点击区域 | 清楚的动词标签、可见禁用/处理中状态、触控目标验收 |
| [Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields) 与 [Writing](https://developer.apple.com/design/human-interface-guidelines/writing)：搜索范围清楚、错误有可行动指引、术语一致 | 搜索标签和清除入口明确，双语错误与状态术语表统一 |

`shadcn` 技能来源为用户提供的 [`shadcn-ui/ui` 仓库](https://github.com/shadcn-ui/ui)，本地已安装在 `/Users/hanming/.codex/skills/shadcn/SKILL.md`。实现时遵守其组件查询、文档读取、CLI 安装、源码复查、语义色/变体、Field/Group/Alert/Empty/Skeleton、弹层标题和焦点等规则。视觉方向采用安静、紧凑、表格优先的企业工作台；品牌森林绿与红色只承载导航和主要动作，警示/成功使用独立语义色，避免装饰性渐变和卡片堆叠。

## 成功条件与尚未解决的限制

成功要求 R01–R13 均有测试或浏览器证据；17 个自定义界面和原生业务实体矩阵没有重大回归；构建产物确实含 shadcn 源组件；无真实客户资料进入测试、截图或 Git。现阶段 Apple HIG 与 shadcn 接入的具体 CSS 隔离机制、Espo 的脚本加载时序和弹层 portal 容器尚未运行时证明；它们是第一实施门槛，不视为已完成。
