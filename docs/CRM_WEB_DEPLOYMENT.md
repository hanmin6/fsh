# CRM Web 部署手册

本手册只覆盖 CRM Web，正式入口是 `https://gzfusanhesp.com`。独立站
`https://fshfoodingredients.com/zh` 不属于本次部署，不修改它的 DNS、代码或证书。

> 2026-10-09：当前 CRM 与渠道采集运行在 22005 Linux，22001 原 Windows 系统已退役。Dify 与采集端的目录、SSH 入口和恢复方法见 [迁移与运维记录](MIGRATION_22001_TO_22005_2026-10-09.md)。本手册的 Caddy 部分仍为备用方案。

## 1. DNS 与防火墙

**2026-10-02 生产环境已采用加拿大 Nginx + 堡垒机 SSH 转发，DNS 无需改到公司出口。**
生产拓扑、验收和回滚见 [CRM_PRODUCTION_EDGE.md](CRM_PRODUCTION_EDGE.md)。
下文直接暴露 Caddy 的方式是备用部署方案，不是当前生产入口；当前更新只执行
`docker compose --env-file /home/fusanhe/fusanhe-crm/server.env up -d`，不要启用 `edge` profile。

在域名服务商处只为 CRM 配置一条记录：

```text
gzfusanhesp.com  A  <CRM 服务器公网 IPv4>
```

如果使用 IPv6，再单独配置 `AAAA`；没有可用 IPv6 时不要填假的地址。等待公共 DNS
解析到 CRM 服务器后再申请证书。服务器安全组和主机防火墙只需要开放 TCP `80`、`443`
（以及 DNS 服务商要求的验证流量）；不要开放 `8080`、`8081`、`3306`。

## 2. 服务器环境文件

在服务器上复制 `.env.example` 为一个只允许管理员读取的文件，例如
`/opt/fusanhe-crm/server.env`，然后替换所有 `change-me`、`replace-with` 和空的密钥。
密钥只保存在服务器环境文件或密钥管理器中，不提交 Git。

生产环境至少确认以下值：

```dotenv
CRM_DOMAIN=gzfusanhesp.com
CRM_PUBLIC_ORIGIN=https://gzfusanhesp.com
ESPOCRM_SITE_URL=https://gzfusanhesp.com
ESPOCRM_BIND_ADDRESS=127.0.0.1
ESPOCRM_WEBSOCKET_BIND_ADDRESS=127.0.0.1
ESPOCRM_WEBSOCKET_URL=wss://gzfusanhesp.com/ws
CADDY_HTTP_PORT=80
CADDY_HTTPS_PORT=443
FUSANHE_PUBLIC_WORKSPACE_ENABLED=false
FUSANHE_OUTBOUND_PAUSED=true
```

`ESPOCRM_ADMIN_PASSWORD`、`DB_ROOT_PASSWORD`、`DB_PASSWORD` 和自动化令牌必须使用
独立的随机值。员工不共享管理员账号；管理员在 EspoCRM 内创建员工账号、分配角色，
员工使用普通用户名和密码登录。

## 3. 启动与重建

在仓库目录执行：

```bash
docker compose --profile edge --env-file /opt/fusanhe-crm/server.env up -d
docker compose --profile edge --env-file /opt/fusanhe-crm/server.env exec -T espocrm bin/command rebuild
docker compose --profile edge --env-file /opt/fusanhe-crm/server.env ps
```

`edge` profile 会启动 Caddy。Caddy 将 HTTP/HTTPS 请求转发到 EspoCRM，将 `/ws` WebSocket
请求转发到内部 WebSocket 服务，并把证书和配置保存到 Docker named volumes。首次启动时
需要服务器能从公网访问 `80/443`，Caddy 才能自动申请证书。

## 4. 验证入口

DNS 生效后，在服务器外部执行：

```bash
curl -I http://gzfusanhesp.com
curl -fsS -I https://gzfusanhesp.com
```

HTTP 应跳转到 HTTPS；HTTPS 应返回 CRM 的响应并通过证书校验。浏览器打开
`https://gzfusanhesp.com` 后，应看到福三和品牌登录页，使用管理员创建的员工账号登录。
登录失败时先检查 `docker compose ... logs --tail=200 espocrm caddy`，不要开启公共工作台
来绕过账号问题。

## 5. 备份、更新与回滚

更新前先备份 MariaDB 和 EspoCRM 数据卷，并保存当前 Git revision：

```bash
git rev-parse HEAD
set -a; . /opt/fusanhe-crm/server.env; set +a
docker compose --env-file /opt/fusanhe-crm/server.env exec -T db \
  mariadb-dump -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" > /opt/backups/crm-$(date +%F).sql
```

备份文件应放在服务器受限目录或独立备份存储，不提交仓库。回滚时切回上一个已验证的
Git revision，保留数据库备份，重新执行 `up -d` 和 `bin/command rebuild`；不要直接删除
`db-data` 或 `espocrm-data` volumes。若新版本有不可逆的数据迁移，先按发布说明确认回滚
路径再操作。

## 6. 运行边界

- CRM Web 是当前唯一维护的用户入口；桌面端和 Android 代码仅作为历史归档。
- `FUSANHE_PUBLIC_WORKSPACE_ENABLED=false` 时，固定的 `**workspace:public-workspace`
  标记必须被拒绝。只有隔离演示环境才允许显式开启。
- `FUSANHE_OUTBOUND_PAUSED=true` 保持默认值，完成真实平台发送验收前不要改为 `false`。
- 不把数据库、EspoCRM 或 WebSocket 的内部端口映射到公网；公网边界只由 Caddy 暴露。
- 本手册不包含独立站的部署、DNS、证书和内容发布操作。
