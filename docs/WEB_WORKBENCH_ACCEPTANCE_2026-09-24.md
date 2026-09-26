# Web 工作台独立验收记录（2026-09-24）

验收对象：`codex/web-workbench-hig` 工作树、隔离站 `http://localhost:18082`，合成测试库；未访问 `localhost:8080`。本记录只覆盖实际检查过的状态。浏览器为 Codex 内嵌浏览器，当前登录账号的 UI 语言为英语；没有提交、审批、外发或改动客户记录。

## 结论

**Web 工作台暂不能判定完成。** 搜索、行链接和已测英文词条已复验通过；有权管理员的原生行业页白屏 N01 也已修复并复验了代表性列表与详情。六个指定视口下，已加载的客服页和会话详情没有整页横向溢出；老板页在 870px 和六个指定视口下也没有整页横向溢出，宽表格位于局部横向滚动容器内。这些结果不等同于 200% 缩放、暗色、高对比和多角色通过。

## 阻断与缺陷

| 编号 | 级别 | 复现与观察 | 影响 |
| --- | --- | --- | --- |
| A01 | 权限边界已核实 | 当前 `boss-history-demo` 账号直接打开 `#AutomationAgent`、`#FusanheProduct`、`#FusanheInquiry`、`#FusanheQuote`、`#FusanheSalesOrder`、`#ExternalChannel` 均显示 Espo 404。主任务经管理员只读 API 查该用户的“老板”角色：六个 scope 均未授予读取，`ExternalConversation` 为 read=all；管理员 `/Metadata` 含六个实体且 controller 为 `controllers/record`。Espo 对无权账号删除这些前端元数据，故路由回退报 404。 | 当前账号的 404 符合 ACL 隐藏，不能算页面故障。R01/R06/R12 仍需有权合成账号实测原生页。 |
| A02 | **已复验** | 旧部署中英文 `#ExternalConversation` 列表 27 行，Search 输入 `SEC-CONV` 后为 0–0 / 0。新部署刷新后相同查询返回 1–3 / 3，Clear filters 可恢复完整列表。 | 可见会话编号搜索缺陷已修。 |
| A03 | **已复验** | 旧部署中无关联客户的行仅 `<tr tabindex="0">` 可操作。新部署刷新后首列有明确 `Open conversation` 链接，目标为相应 `#ExternalConversation/view/{id}`。 | 记录入口具备链接语义；整行 Enter 操作仍可用。 |
| A04 | **已复验** | 旧部署英文发送状态露出 `claimed`/`cancelled`，会话原生字段露出 camelCase 键。新部署的状态下拉显示 `Claimed`/`Cancelled`；会话面包屑为 `Conversations`，原生区域显示 `Name`、`Status`、`Assigned user` 等译名。 | 已测字段和状态词条修复；其它页面中英全矩阵仍待测。 |
| A05 | **已复核** | 390px 会话详情的面包屑现在以 `Conversations` 开头，长记录名仍在顶栏末端截断；紧接其下的工作区副标题完整显示该记录名，返回链接可见。 | 当前未见关键路径受遮挡；200% 缩放仍待测。 |

## 已实测页面和操作

- `#Home`、`#Home/crm`、`#Home/service`、`#Home/insights`：均加载真实指标、最近记录或历史建议；老板页对平台可见总量和同步失败显示 “Needs verification”，保留上海时区标识和证据链接。`#Home/insights` 的 870px 表格左右内容在局部容器滚动，无整页溢出。
- `#Home/service` → `#Home/insights` → 浏览器后退 → 前进能恢复对应页面；`#Home/service` → 原生 `#Account` → 后退时 `[data-fsh-ui-root]` 数量依次为 1、0、1，没有重复根。
- `#ExternalConversation`：27 行载入；筛选/清除结果如 A02 修复前后记录；首行按 Enter 或点显式链接可进入 `#ExternalConversation/view/{id}`。详情可见时间线、原文、身份状态、停发提示与原生关系区。390px 的 “Profile & review” 标签可点击，键盘 ArrowLeft 可从该标签切回 “Messages”；当前账号对身份确认与任务创建显示无权限文案，未尝试提交。
- `#AIReplyDraft`、`#KnowledgeDocument`、`#OutboundTask`：页面可打开，当前测试库显示空态；知识文档保留仅已批准且有效期资料可用的提示；发送任务最终状态显示停发。它们的详情页因无可用记录未测。`#AutomationAgent` 受 A01 阻断。
- `#Account/view/{id}`、`#Lead/view/{id}`：客户概览和原生字段/关系区域加载，缺失值与线索状态可辨；`#Contact` 有入口但当前测试库无记录，详情未测。
- 原生 `#Lead` 与 `#Task` 列表可达；390px 原生 Lead 表格保持局部滚动、整页未横溢。产品、询盘、报价、订单等原生实体在当前账号下因 A01 不可达，编辑表单和弹层未测。

### 响应式实测

通过浏览器视口控制逐一设置 `1920×1080`、`1440×900`、`1280×720`、`1024×768`、`768×900`、`390×844`，对已加载的客服页、会话详情检查 `document.documentElement.scrollWidth <= innerWidth + 1`，六组均成立。客服页 390px 的表格父容器为 `overflow-x: auto`，例如内容宽 881px、容器宽 347px；老板页额外检查 870×900，建议表同样为局部滚动。没有把原生编辑页纳入六视口矩阵，也没有浏览器缩放 200% 的运行证据。

## R01–R13 判定

| 要求 | 本轮结果 | 依据或缺口 |
| --- | --- | --- |
| R01 导航/路由 | **部分** | A01 的 404 已核实为当前账号无权；有权账号仍待测。已测 Home/CRM/客服/老板/询盘路由可达，客服→老板→后退→前进均恢复目标页。 |
| R02 工作台与列表 | **部分** | A02 会话编号搜索在新部署复验为 3 条，清除可恢复 27 条；其它列表筛选/排序未完整遍历。 |
| R03 状态反馈 | **部分** | 老板“Needs verification”、停发提示和空态实际可见；局部错误/成功/处理中未全面注入。 |
| R04 会话信息 | **部分** | 时间线、身份、审核区和关系区在当前合成记录可见；其它会话状态未全覆盖。 |
| R05 审批/停发/权限 | **部分** | 当前只读受限操作文案与停发可见；没有执行审批确认或跨角色浏览器矩阵。 |
| R06 客户和原生实体 | **部分** | Account/Lead 可达；A01 下的业务实体未用有权账号复验；Contact/上下文详情无记录。 |
| R07 视口/缩放/触控 | **部分** | 六视口客服与会话、七视口老板无整页横溢；200% 和粗指针 44px 未测。 |
| R08 键盘/语义/对比 | **部分** | Enter 行导航、显式详情链接和会话标签方向键可用；未完成 Axe、读屏、对比度矩阵。 |
| R09 中英/时间 | **部分** | A04 已测英文枚举和原生字段修复；中文 UI 与其它页面尚未全量实测。老板页上海时区可见。 |
| R10 主题/高对比 | **未测** | 未切换暗色、强制高对比或系统字体放大。 |
| R11 shadcn 构建 | **部分** | 页面有 React 内容，组件与 AMD 测试通过；本轮未重复 `npm ci`/完整构建或官方 CLI 识别。 |
| R12 Espo 共存 | **部分** | 已测原生 Lead/Task 可用，离开/返回 React 页面根数为 1→0→1；A01 已核权，但其余原生路由仍需有权账号实测。 |
| R13 代表页/回退 | **部分** | 代表性页面可达，旧回退有自动测试；本轮未做实际回退部署演练。 |

## 独立命令复核

2026-09-24 23:13–23:24 CST，在隔离工作树运行以下命令，均退出 0：`make spec-check SPECIFY_FEATURE_DIRECTORY=specs/004-web-workbench-hig`；`node --test client/custom/tests/frontend.test.cjs client/custom/tests/home-react-mount.test.cjs`（22/22）；`npm --prefix client/custom/ui test`（首次 30/30，修复后再次运行 7 文件、31/31）；`git diff --check`。本轮未重跑完整安全回归、PHP app-check、`npm ci` 或构建；主任务既有证据不能替代独立复测。

## 未覆盖及复验条件

需用有权账号实测 A01 涉及的路由，再补齐 Contact、三种上下文详情、其余原生行业实体的列表/详情/编辑/关系/弹层；至少使用老板、销售、客服、只读及无权合成账号。另须实测中英两套 UI、亮/暗/高对比、200% 缩放、键盘完整任务流、焦点回退、Axe 或等效语义扫描、粗指针目标尺寸、审批确认前流程和实际回退演练。所有复测继续只在 18082 隔离合成库进行。

## 2026-09-26 继续开发与待复验

独立静态审查指出：会话受控弹窗缺少触发器时，关闭后焦点不能可靠回到原操作；短视口下弹窗底部可能不可达；移动分区标签与内容缺少语义关联；草稿/发送队列缺少本记录详情链接；列表数组会误译与状态名相同的客户/模型文本。主任务已增加焦点返回与单元测试、弹窗视口内滚动、可本地化关闭标签、分区 `aria-controls`/`tabpanel`、局部横向滚动、显式详情链接，并让业务文本原样显示。UI 34/34、AMD 28/28、产物校验和 `git diff --check` 通过。**这些静态及组件修复仍需浏览器复验，尤其 200% 缩放、弹层焦点、中文与暗色主题。**

## 有权账号原生业务页复验（2026-09-26）

本段仅针对 `http://localhost:18082` 的隔离合成库。先以该栈管理员凭据执行只读 API/元数据检查；不涉及 `8080`、权限改动或业务写入。管理员 `/Metadata` 均注册了下列实体；目标业务实体的 `clientDefs` 指向 Espo 原生 `controllers/record`，`ExternalIdentity` 使用默认控制器。下表的 API 成功只证明服务端记录可读，不能代替浏览器界面验收。

| 实体 | 管理员 API 列表总数 | 首条详情 API | 浏览器页面 |
| --- | ---: | --- | --- |
| AutomationAgent | 17 | 200 | 自定义列表 17 条可见；首条原生详情可打开，字段与 Stream 可见 |
| FusanheProduct / FusanheProductSpec | 3 / 3 | 均 200 | 两个原生列表均空白；产品详情空白 |
| FusanheCertificate / FusanheSample | 3 / 3 | 均 200 | 待测 |
| FusanheInquiry | 0 | 无合成记录 | 原生列表空白，连空态都未呈现 |
| FusanheQuote / FusanheQuoteItem | 3 / 0 | 报价 200；明细无记录 | 报价原生列表空白；明细待测 |
| FusanheSalesOrder / FusanheOrderLine / FusanheOrderShipment / FusanheShipmentItem | 均 0 | 无合成记录 | 订单原生列表空白；其它待测 |
| ExternalChannel / ExternalIdentity / ExternalMessage / AutomationAudit | 10 / 27 / 35 / 57 | 均 200 | 渠道原生列表 10 条、首条详情及 Edit→Cancel 表单可用；其它待测 |

**阻断 N01：** 在隔离管理员会话打开 `#FusanheProduct`（刷新）、`#FusanheProduct/view/6ab53ca2dd20638a4`、`#FusanheProductSpec`、`#FusanheInquiry`、`#FusanheQuote`、`#FusanheSalesOrder`，宿主导航出现但主内容为空白。产品列表控制台报 `TypeError: (e ?? []).forEach is not a function`；产品详情报 `TypeError: this.detailLayout is not iterable`。静态核对发现 11 个 `Fusanhe*` 行业实体的 `list`、`detail`、`detailSmall`、`filters` 共 44 份布局 JSON 顶层是 `{ "layout": ... }` 对象，而正常工作的 `AutomationAgent`/`ExternalChannel` 对应布局是数组。`detail`/`detailSmall` 还须符合 Espo 的面板 `rows` 结构。主任务已收到此缺陷，修复、rebuild 与浏览器复验尚未计入本段。

`#ExternalChannel` 的原生列表、详情与编辑表单在管理员会话中可见，点击 Cancel 后回到只读详情且没有提交；`#AutomationAgent` 的 17 行列表及首条原生详情可见。未测试这两页的关系面板、新建、保存、键盘全流程或窄屏。行业实体的编辑/关系/弹层因 N01 无法验收，R01、R06、R12 仍为部分，不可判定通过。测试结束时已将共享浏览器留在 `#Home/service`。老板合成账号此前的 Dark 偏好仍待主任务恢复。

### N01 修复后复验（2026-09-26）

主任务将 11 个行业实体的 44 份布局改为 Espo 原生数组结构；详情与简版详情使用 `[{"rows":[...]}]` 面板结构，字段和顺序保持原样。`tests.test_contracts` 新增全部布局结构检查并通过 6/6；独立静态 Agent 逐文件核对原字段与顺序无丢失。隔离栈 `rebuild`、`app-check` 均退出 0。

管理员在隔离浏览器重新加载后，`#FusanheProduct` 显示 1–3 / 3 与产品链接，首条详情显示名称、状态、编码等字段；`#FusanheProductSpec`、`#FusanheCertificate`、`#FusanheSample`、`#FusanheQuote` 均显示 1–3 / 3，首条报价详情显示报价编号、客户、币种等字段。`#FusanheInquiry` 和 `#FusanheSalesOrder` 显示 0 / 0 与 No Data 空态，不再白屏。修复后尚未逐一打开其余行业实体详情、编辑和关系面板，也未以销售/客服/只读角色测试权限。

本轮另修复指针点击弹窗触发器时的焦点记录：人工草稿弹窗在管理员会话打开、关闭后，焦点回到 `Manual draft` 按钮；整页刷新后英文关闭按钮为 `Close`。390×320 短视口时弹窗位于视口内，内容区域 `overflow-y: auto`，`scrollHeight` 447px、`clientHeight` 299px；390×844 会话页无整页横向溢出。1440px 宽时三栏面板不再保留隐藏标签对应的 `tabpanel` 与额外 Tab 停靠点；390px 宽时三个面板均通过 `aria-labelledby` 关联可见标签。这些是指定场景的浏览器证据，尚未完成 200% 浏览器缩放和完整 Axe/读屏矩阵。

继续逐类检查时，11 类 `Fusanhe*` 原生列表均加载：有数据的产品、规格、证书、样品、报价显示 1–3 / 3；其余六类显示 0 / 0 与 No Data。产品、规格、样品、报价的首条详情可读。证书详情曾再次白屏，控制台报 `views/fields/attachments-multiple` 脚本不存在；`FusanheCertificate.files` 保留 Espo 标准 `attachmentMultiple` 类型并移除错误的自定义视图路径后，隔离栈再次 `rebuild`、`app-check`，刷新证书详情显示证书名称、状态、类型、有效期和 Files 等字段。Edit 表单可打开并显示 Attach File 控件，Cancel 返回只读详情，未保存记录。布局之外的此项修复加入离线契约检查。行业实体关系面板、其余详情及角色权限仍未全面验收。

独立静态 QA 还发现老板页英文界面中，服务端固定的中文覆盖说明和建议动作因保护业务原文的改动而未翻译。主任务改为只翻译已知固定服务端模板，其余客户与模型文本保持原样；中英词条补齐两条覆盖对账提示，组件测试同时覆盖这两类文本。分析详情的大段 `aria-live` 已移除，避免一次播报整份画像；结果可见性和焦点顺序仍需真实读屏复验。

再次构建并刷新隔离管理员的英文 `#Home/insights` 后，覆盖说明和固定建议动作显示英文，历史表格保留 6 列。点击首行 `View analysis` 后，焦点移至 `Customer analysis` 二级标题，页面滚动到分析区，按钮 `aria-expanded=true`；未执行读屏工具测试。多渠道覆盖原因若拼接不同固定句，仍可能保留中文，R09 保持部分。

### N01 修复后的结构检查（浏览器复验待补）

主任务已将 11 个行业实体的 44 份布局改为 Espo 所需的数组形态，并为 `detail`/`detailSmall` 配好面板 `rows`。主任务报告隔离栈 `rebuild`、`app-check`、Compose config、`spec-check` 退出 0，结构回归 `python3 -m unittest tests.test_contracts` 为 6/6，扩展离线合同测试为 46/46。这些是代码与运行环境检查，**尚不能将 N01 标为浏览器复验通过**。须在有权账号下重新访问上表六个此前空白的路由和至少一个产品详情，核对控制台无同类异常，并验证原生编辑与关系区。
