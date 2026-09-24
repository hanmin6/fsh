# 福三和 Web 工作台组件层

EspoCRM 仍负责登录、导航、ACL、原生记录页和业务 API。本目录只构建自定义内容区的 React + TypeScript 界面。组件源码由官方 shadcn CLI 安装，项目配置见 `components.json`。

## 构建与复现

```sh
npm ci --prefix client/custom/ui
npm --prefix client/custom/ui run build
npm --prefix client/custom/ui run typecheck
npm --prefix client/custom/ui test
npm --prefix client/custom/ui run check:generated
```

构建输出为同源静态文件 `client/custom/src/fusanhe/ui-runtime.js` 和 `client/custom/res/fusanhe/ui.css`，二者纳入 Git。它们由 `scripts/emit.mjs` 从 Vite UMD 产物生成，前者注册为命名 AMD 模块 `custom:fusanhe/ui-runtime`，后者将每条样式规则限制在 `[data-fsh-ui-root]` 内。Tailwind Preflight 不导入。组件弹层的 Radix portal 挂在同一根节点中。

## 页面接入契约

React 页面放在 `src/screens/<package>/<id>.tsx`，默认导出接受 `ScreenProps<T>` 的组件，文件名即页面 ID；也可导出 `screenId`。入口使用 Vite glob 自动收集，无需共同编辑注册文件。HostBridge 类型在 `src/lib/host.ts`。请求经 Espo Ajax，权限经 Espo ACL，链接经 Espo Router。

AMD 视图继承 `custom:views/fusanhe/react-host`，渲染一个 `.fsh-ui-mount` 元素后调用：

```js
const mounted = await this.mountScreen("service", data, this.$el.find(".fsh-ui-mount")[0]);
if (!mounted) this.loadLegacyView();
// 数据变化：this.updateScreen(data)
// remove() 会自动卸载；异步装载经过 generation 检查。
```

`getOutboundState()` 仅接受服务端 `outboundPaused` 的布尔值。字段缺失、无权限或请求失败时返回 `{ paused: null, status: "unknown" }`，界面不能将未知当成未停发。React 组件不持有令牌、不调用独立 fetch、不绕过既有人工审核与二次确认。
