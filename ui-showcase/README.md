# 福三和 UI 展示

从仓库根目录启动本机静态服务：

```sh
python3 -m http.server 8766 --bind 127.0.0.1
```

打开 <http://127.0.0.1:8766/ui-showcase/>。无需 Docker、CRM 登录、API 密钥或 npm 安装。

## 展示范围

- **原版 Web React 页面**：首页、CRM、AI 客服、历史客户、五类队列、会话详情、Account/Contact/Lead 客户概览，以及 AI 草稿/知识文档/发送任务提示。页面主体直接加载 `client/custom/src/fusanhe/ui-runtime.js` 与 `client/custom/res/fusanhe/ui.css`。导航和虚构数据位于本目录。
- **登录和 Espo 原生页**：展示页面目录、源码入口和运行限制。登录表单仅是结构示意；原生列表、编辑、关系面板需在 EspoCRM 中查看。
- **Android**：列出 Compose 页面与源码。没有 Android 模拟器截图时不制作替代性的网页画面。

`fixtures.js` 只包含虚构的 `.example` 联系方式。`showcase.js` 的 HostBridge 将写操作拒绝、权限限制为只读，外发状态固定为暂停。展示页不会读取 `.env`、Cookie 或 CRM 数据，也不会向 CRM 发请求。

更新原版 React 页面后，先在 `client/custom/ui/` 运行项目原有构建命令，展示页会自动加载更新后的受版本管理产物。移除展示页时删除 `ui-showcase/` 即可，不影响 CRM。
