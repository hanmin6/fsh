# CRM 公网入口：2026-10-02

正式入口：https://gzfusanhesp.com 。HTTP 和 www 跳转到此地址。
DNS 保留加拿大服务器地址，原来跳到独立站的规则已移除。

## 实际链路

浏览器 → 加拿大 Nginx（187.52.122.192:443，TLS 终止）→ 加拿大 loopback
18085/18086 → SSH 加密通道 → 堡垒机（8.138.165.27）→ 现有 22005
公司反向 SSH 通道 → 公司服务器（192.168.0.13）8080/8081。

- 18085 是 CRM HTTP，18086 是 WebSocket；两台中转服务器均只监听 loopback。
- 堡垒机 systemd：`fusanhe-crm-origin.service`、`fusanhe-crm-edge.service`。
  两者已 enable，5 秒重试，15 秒心跳、3 次未响应退出重连，并校验 SSH 主机公钥。
- 专用私钥仅存堡垒机 `/etc/fusanhe-crm-tunnel/edge_ed25519`，不进 Git。
  加拿大授权限制为两个指定远端监听端口，禁用交互终端和正常命令执行。
- 加拿大配置：`/www/server/panel/vhost/nginx/gzfusanhesp.com.conf`。
  运行中的 Nginx：`/www/server/nginx/sbin/nginx`，主配置
  `/www/server/nginx/conf/nginx.conf`。
- 沿用宝塔站点证书（本次检查有效期至 2026-11-22），保留 HTTP ACME 验证目录。
  本次未触发证书续期，自动续期是否成功仍需后续在到期前确认。
- 公司部署目录：`/home/fusanhe/fusanhe-crm/current`；环境文件在上级 `server.env`。
  公司 Caddy 已停止并关闭容器自动重启；不要使用 `--profile edge` 重建它。
- 独立站的 DNS、站点配置和应用未修改。

## 验收

- 公网 HTTPS 200，证书校验通过，内容为 EspoCRM。
- HTTP 301 到 HTTPS CRM。
- 通过公网 `/api/v1/App/user` 使用服务器管理员凭据验证：200。
- 固定公共工作台凭据：401。
- `/ws` 携带 `Sec-WebSocket-Protocol: wamp`：101 Switching Protocols。
- 两个 SSH 服务已启用开机启动，重启服务后再次验证公网入口。
- 独立站 `/zh` 返回 200，站点配置 SHA256 保持
  `24526be1afeed7c1e4f847984059cc0cf0237a015015b5b10b916d6d4821d4c4`。
- 发信仍暂停，图片生成仍禁用；本次未进行真实发送或付费模型调用。

## 运维与回滚

堡垒机检查：`systemctl status fusanhe-crm-origin fusanhe-crm-edge`，
日志：`journalctl -u fusanhe-crm-origin -u fusanhe-crm-edge`。
加拿大检查：`curl -I http://127.0.0.1:18085/`。
公司检查：进入 current 后运行 `docker compose --env-file ../server.env ps`。

切换前的域名配置备份：加拿大 `/root/gzfusanhesp.com.pre-crm-20261002.conf`。
如需恢复旧跳转，复制回站点配置，运行 Nginx `-t` 校验，再 `-s reload`；
两条命令均指定上述主配置。不要删除 CRM 数据卷。
SSH 授权备份：加拿大 `/root/.ssh/authorized_keys.pre-crm-20261002`。
停用转发时，在堡垒机 `systemctl disable --now fusanhe-crm-edge fusanhe-crm-origin`，
再从加拿大授权文件仅移除注释为 `fusanhe-crm-edge` 的专用密钥行。

这是多节点单链路部署，没有高可用切换。任一节点、公司供电或网络中断均可导致
CRM 不可用；SSH 自动重连仅处理链路恢复后的重建，不代替数据库备份或节点冗余。
