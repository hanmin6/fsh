# 公司宽带直接接入

目标：`https://fshcrm.xyz` → 公司宽带路由器 → 广州主机 HTTPS 代理 → 回环 CRM/WebSocket。此目录是准备好的配置，当前未启动、未设置路由映射、未改 DNS。

2026-10-20：主机 192.168.0.13/23，默认网关 192.168.1.1，无公网 IPv6。反向 SSH 的出口地址 14.19.154.56 只证明出口，必须登录网关核对 WAN，不能直接当作可入站公网地址。用户暂时没有网关管理员账号，直连待此条件满足。

启用前由网络管理员核对：

1. WAN 是可入站的公网 IPv4；若处于运营商 NAT，向电信确认公网接入方案。
2. 电信允许该宽带对外提供 HTTPS，满足其端口、备案及相关接入要求。
3. 为主机保留 192.168.0.13，确认本机 80/443 未被其他服务占用。
4. 仅映射 TCP 443 → 192.168.0.13:443；默认自动证书及 HTTP 跳转还使用 TCP 80 → 192.168.0.13:80。数据库、SMB、SSH、VNC、Dify 和 CRM 原始端口不做此映射。禁用路由器公网管理或处理其与 web 入口的端口冲突，不能开放管理后台。
5. 核实动态地址策略；如需 DDNS，凭据单独保管并仅允许更新该域名记录，不写进此目录。

先验证配置：

```sh
docker compose -f deploy/company-broadband/compose.yaml --profile direct config --quiet
docker run --rm --network none -e CRM_DOMAIN=fshcrm.xyz -e CRM_BIND_ADDRESS=192.168.0.13 -v "$PWD/deploy/company-broadband/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile
```

满足前提后再启用：

```sh
docker compose -f deploy/company-broadband/compose.yaml --profile direct up -d
```

将域名 A 记录切到已核实的公司 WAN 地址后，从外部网络验证严格 TLS、Espo 账号登录、匿名接口拒绝及 WebSocket。公司内网如不支持 NAT 回流，配置内网 DNS 指向 192.168.0.13；外网 DNS 不指向私网地址。

回退：恢复原 DNS，停止本目录的 direct profile，删除本次专门创建的路由转发规则。保留证书卷，CRM、数据库与业务文件保持原位置。
