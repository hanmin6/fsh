# Web 工作台 shadcn/ui 重构交接

本文件对应 `codex/web-workbench-hig` 分支。需求、架构、任务与逐项验收证据分别见 [`spec.md`](../specs/004-web-workbench-hig/spec.md)、[`plan.md`](../specs/004-web-workbench-hig/plan.md)、[`tasks.md`](../specs/004-web-workbench-hig/tasks.md) 和 [`verification.md`](../specs/004-web-workbench-hig/verification.md)。本文只记录接手实现和发布所需的稳定入口；是否完成以验收账本为准。

## 实现边界

- EspoCRM 10.0.8 仍管理登录、ACL、路由、原生实体 CRUD、关系面板及业务状态机。新 React 层只挂载自定义内容区。不得把前端权限判断当成服务端授权。
- `client/custom/ui/` 是独立 React、TypeScript、Vite、Tailwind v4 工程。`components.json` 指定 Radix 基础组件与 Lucide；`src/components/ui/` 是官方 shadcn CLI 安装的组件源码，构建产物提交到 `client/custom/src/fusanhe/ui-runtime.js` 和 `client/custom/res/fusanhe/ui.css`。运行时不依赖 CDN 或 npm 服务。
- `client/custom/src/views/fusanhe/react-host.js` 把 Espo Ajax、ACL、路由、翻译、通知、当前用户和停发状态传给屏幕。`src/entry.tsx` 自动发现 `src/screens/**/*.tsx` 的默认导出，`screenId` 指明宿主调用名称。宿主卸载时必须销毁 React root，迟到响应须被忽略。
- `ui.css` 的所有选择器限制在 `[data-fsh-ui-root]`；构建脚本会拒绝非作用域规则。`brand.css` 保留 Espo 壳层，`native.css` 负责原生页面适配。React 根跟随 Espo 实际主题，不能只根据系统暗色偏好切换。
- 业务状态继续以服务端为准。外发开关未知时显示“状态未知”；批准草稿只生成受控发送任务，不能直接发送。隔离测试环境保持 `FUSANHE_OUTBOUND_PAUSED=true`。

## 页面与文件所有权

| 页面组 | 路由/入口 | 主要源码 |
| --- | --- | --- |
| 首页、CRM、客服、老板页 | `#Home`、`#Home/crm`、`#Home/service`、`#Home/insights` | `client/custom/src/views/fusanhe/{home,crm-home,service-home,insights}.js`；`client/custom/ui/src/screens/{dashboard,insights}/` |
| 五类队列列表 | ExternalConversation、AIReplyDraft、KnowledgeDocument、OutboundTask、AutomationAgent | `client/custom/src/views/fusanhe/list.js`；`client/custom/ui/src/screens/queue/` |
| 会话详情 | `#ExternalConversation/view/{id}` | `client/custom/src/views/external-conversation/record/detail.js`；`client/custom/ui/src/screens/conversation/` |
| 客户与上下文详情 | Account、Contact、Lead、AIReplyDraft、KnowledgeDocument、OutboundTask | `client/custom/src/views/fusanhe/{customer-detail,context-detail}.js`；`client/custom/ui/src/screens/customer/` |
| 登录、Dashlet、原生业务实体 | Espo 原有路由 | `client/custom/src/views/fusanhe/login.js`、`client/custom/src/views/{dashlets/fusanhe-operations,fields/structured}.js`、`client/custom/res/fusanhe/native.css` |

列表和详情页面必须保留原生字段、关系面板和既有动作语义。新增静态 UI 文案使用 `host.translate(中文词条)`，英文词条集中在 `custom/Espo/Custom/Resources/i18n/en_US/Fusanhe.json`，客户原文和草稿正文不经翻译。

## 开发与验证

```sh
npm ci --prefix client/custom/ui
make web-check
node --test client/custom/tests/frontend.test.cjs
make spec-check SPECIFY_FEATURE_DIRECTORY=specs/004-web-workbench-hig
make verify-offline
```

页面源码变化后，单独运行 `npm --prefix client/custom/ui run build` 更新受版本管理的 JS/CSS 产物；`make web-check` 中的 `check:generated` 验证没有产物漂移。并行改页面时只由集成者构建，避免多个 Agent 同时写产物。PHP 改动还须在隔离栈运行 `bin/command app-check`、相关 lint 和安全回归。

浏览器验证使用 `http://localhost:18082` 的 `fusanhe-phase1-test` 隔离合成库。`http://localhost:8080` 是主环境，不能注入测试记录。登录、客户数据、Cookie、密钥、真实 Alibaba 资料及未脱敏截图不得提交 Git。当前验收矩阵涵盖 17 个自定义 Web 界面、原生实体页、中文/英文、六种视口、200% 缩放、键盘焦点、暗色/高对比和多角色权限；实际通过/未覆盖状态见 `verification.md`，不能从测试命令成功推断视觉验收完成。

## 发布与回退

发布时先确认源代码和 `ui-runtime.js`/`ui.css` 产物一致、`native.css` 已包含、`client.json` 资源顺序正确，并在目标环境执行 Espo rebuild/app-check。保留发布前的静态资产和 Espo 配置快照；切换后完整刷新浏览器，实测 `#Home/service`、原生 Account 列表、会话详情与老板页。若新屏幕装载失败，AMD 页面保留旧内容回退路径；完整回退须恢复旧版资源和入口并复测，而非只撤销 Git 提交。

本分支不完成 Android 重构、真实 Alibaba 全历史回填或真实外发。这三项各有独立环境与验收要求，不应在 Web 验收时标为已完成。
