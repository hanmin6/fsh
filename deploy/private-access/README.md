# 公司内网和远程私有访问

用户选择先使用私有组网。同事在广州公司局域网内，远程操作者不在该局域网。统一目标地址为 `http://192.168.0.13/`，保留 Espo 账号登录。

## 两条访问路径

- 公司内网：公司电脑 → `192.168.0.13:80` → Caddy → 原有 CRM / WebSocket 回环端口。
- 远程设备：NetBird 客户端 → 加密组网 → 广州 rootless routing peer → 同一个 `192.168.0.13:80`。

办公网段目前为 `192.168.0.0/23`。Caddy 只监听主机 LAN 地址，只接受该办公网段和指定组网容器地址。入口使用办公内网 HTTP；远程跨互联网部分由 WireGuard 加密，数据在公司内网端终止。公网域名和 DNS 不作改动，不映射公网端口。

NetBird 使用独立 bridge 容器，无 host 网络、TUN、NET_ADMIN、特权模式或主机目录挂载。其状态在独立 Docker 卷中保存，配置固定官方 rootless 0.81.3 镜像摘要。容器地址 `172.30.93.2` 和网络 `172.30.93.0/29` 需在启用前检查无冲突。

若主机无法连接官方镜像仓库，可从官方 registry 下载并逐项验证 manifest、config、压缩层和解压后 DiffID，在主机导入后核对 Config/RootFS。Docker 使用 containerd 存储时，导入后的 manifest 摘要可能因格式转换而变化；运行时 `.env` 的 `NETBIRD_IMAGE` 可指向核验后的本地不可变 RepoDigest，并用 `--pull never` 启动。来源与两种摘要记录在服务器 `image-provenance.json`，不使用第三方镜像代理。

## 运行

实际部署目录为 `/home/fusanhe/fusanhe-crm/private-access`，独立于当前应用 release。先验证配置：

```sh
docker compose -f deploy/private-access/compose.yaml --profile vpn config --quiet
docker run --rm --network none --entrypoint caddy \
  -v "$PWD/deploy/private-access/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.10-alpine validate --config /etc/caddy/Caddyfile
```

在实际部署目录启动内网入口，备份应用配置及外部环境文件后，将 `siteUrl` 改为 `http://192.168.0.13`、`webSocketUrl` 改为 `ws://192.168.0.13/ws`。同步外部环境文件的两个 URL，以便将来重建服务时保持一致。使用 Espo ConfigWriter 修改配置并更新前端缓存时间戳；原有数据库和应用容器不需要重建。

```sh
docker compose up -d caddy
docker compose --profile vpn up -d netbird
```

组网必须由用户自己的 NetBird 账号授权，远程设备也加入同一个账号。不要把 setup key、登录令牌、设备私钥或 CRM 密码放入 Git 或聊天。当前官方免费方案允许 5 个用户和 100 台设备，见 [NetBird 定价](https://netbird.io/pricing)。

## 组网授权范围

在 NetBird 后台建立专用 network/resource：

1. Routing peer 选择 `fsh-crm-gz`。
2. Resource 只包含 `192.168.0.13/32`，不发布整个公司网段、默认路由或出口节点。
3. 来源只允许用户授权的远程设备组；策略只允许目的 TCP 80。
4. 不扩大现有 default all-to-all 策略；对本次新组网使用限定访问策略。

远程设备启用该 network 的路由后，直接使用与同事相同的内网地址。若远程所在地已有相同私网地址，检查 `/32` 路由优先级，不能覆盖其他本地网段。若用户本机代理工具拦截私网地址，为这个精确地址设置直连。

## 验收和回退

内网入口需验证页面、匿名 API 401、WebSocket 101、来源限制和核心服务健康。组网需另外验证两端已连接、限定路由/策略、远程页面、登录和实时连接；不能仅凭服务启动就宣称远程访问完成。

来源拒绝应使用真实的非允许源地址测试。主机上的其他 Docker 网络可能经过 SNAT，以主机 LAN 地址访问代理，不能用这种请求来证明不在允许列表的源会被拒绝。Caddy 的拒绝规则与反向代理放在同一个 `route` 中，以保证来源检查先执行。

回退时停止本目录的容器，撤销本次 resource/策略/设备授权，按备份恢复原站点/实时 URL 和对应环境文件。保留业务数据库、附件及原有 SSH 通道；不要删除 NetBird 状态卷后把设备遗留在管理后台。
