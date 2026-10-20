# 公司局域网与 NetBird 私有访问

用户确认先配置公司局域网及其当前 Mac。授权的远程访问范围为 `192.168.0.13/32` 的 TCP 80，只提供 CRM 网页和同端口 `/ws` 实时连接。

## 已完成

2026-10-20 公司内网入口已启用：`http://192.168.0.13/`。独立配置位于 `/home/fusanhe/fusanhe-crm/private-access`，不改变应用 release 指针和业务源码。

- Caddy 绑定 `192.168.0.13:80`，页面 200、匿名 App/user 401、WAMP WebSocket 101。
- Caddy 来源拒绝先于代理执行，绑定非允许的回环源地址验证得到 403。
- Espo `siteUrl=http://192.168.0.13`、`webSocketUrl=ws://192.168.0.13/ws`，保留原生登录和全局停发。
- 外部 `server.env` 原有两组重复 URL 已同步成相同的内网 URL；其他环境项保留。修改前的配置备份位于 `/home/fusanhe/fusanhe-crm/backups/private-access-20261020T052558Z`，附 SHA-256 清单。
- 仅重建 WebSocket 服务以更新其启动环境中的 URL；app、daemon、db 容器 ID 保持一致。最终四个核心服务均 healthy，app-check 通过。
- NetBird 官方 rootless 0.81.3 镜像已下载、核验并导入。主机直接拉取 registry 超时，改在操作者电脑下载官方 registry 的原始内容，核对所有层后通过已有 SSH 导入。运行容器使用核验过的本地不可变摘要，无新增主机特权。
- 用户已自行登录 NetBird；后台显示 Free 方案、1 位用户、首次检查时尚无已注册设备。Mac 官方安装包 SHA-256 与官方发布一致，Apple 安装签名与公证均通过。

上述是主机端验收；未借此声称其他同事的浏览器或远程 Mac 已验收。公网 `fshcrm.xyz` DNS 未改动，没有路由器端口映射，也没有公网入口切换。

## 仍待完成

1. 用户在自己的 NetBird 账号中完成广州主机的设备登录授权。
2. 用户完成 Mac 官方客户端安装所需的本机管理员授权，并用同一个 NetBird 账号连接。
3. 建立指定广州 peer 的单主机 resource、远程 Mac 来源组与 TCP 80 策略，避免发布整段公司网或默认路由。
4. 从 Mac 验证实际组网、到 `192.168.0.13/32` 的路由、页面、原生登录、匿名拒绝和实时连接，再更新最终状态。

具体配置及恢复方式见 `deploy/private-access/README.md`。公司宽带公网直连仍是另一个未完成的方案，不影响本次内网入口已启用的事实。
