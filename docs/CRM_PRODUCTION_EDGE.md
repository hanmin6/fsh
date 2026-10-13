# CRM 公网入口：2026-10-02

## 当前正式入口：2026-10-10

用户已选择在现有 Hostinger 域名下启用 **https://crm.fsh.digital/**。
DNS A 记录指向美国 `31.170.165.252`，HTTPS 和 CRM 转发均已验证。
后台和数据库仍位于公司 22005；原账号认证返回 200，匿名 API 返回
401，WebSocket 返回 101。CRM 持久化 siteUrl、webSocketUrl 和
server.env 已同步更新，相关容器均 healthy。

美国配置为 `/www/server/panel/vhost/nginx/crm.fsh.digital.conf`；
证书为 `/etc/letsencrypt/live/crm.fsh.digital/`，有效期至 2027-01-07，
沿用已启用的 Certbot 自动续期及 Nginx 重载 hook。
新入口继续保留员工 CRM 的 noindex 响应头。

旧域名 gzfusanhesp.com 的管理账号仍未找到，但新入口已可独立使用。
下文有关旧域名 DNS 待切换的内容为此前检查记录，不代表新入口仍待部署。
详情见 `crm-us-migration-20261010/crm.fsh.digital部署完成.md`。

## 2026-10-10：美国入口恢复，DNS 待切换

美国新服务器为 `31.170.165.252`。已经从 22001 的 Edge 中复用
Hostinger 登录，添加专用运维公钥并验证 SSH 成功。该服务器的 CRM
Nginx 配置及原证书已恢复，证书有效期至 2026-11-22。

已恢复的新链路：美国 Nginx → 美国 loopback 18085/18086 → 堡垒机
8.138.165.27 → 公司 22005 → 8080/8081。堡垒机新增
`fusanhe-crm-edge-us.service`，已启用开机启动，沿用现有受限隧道密钥。
美国 SSH 主机公钥单独固定在
`/etc/fusanhe-crm-tunnel/us-20261010.known_hosts`。
仅将 18085/18086 监听在 loopback，未开放为公网端口。

通过 `curl --resolve` 直连新 IP 并保留正常 TLS 校验：CRM HTTPS 200，
HTTP/www 301 到正式入口，匿名用户 API 401，WebSocket 101；CRM 的
noindex 响应头保留，官网返回 200 且未附加 CRM noindex。

**公共 DNS 尚未切换，不能据此认定正式域名已经恢复。**
根域及 www 当前仍解析为旧 IP `187.52.122.192`；NS 为
`ns1.myhostadmin.net`、`ns2.myhostadmin.net`。域名管理账号尚未确认，
22001 的 Edge 中西部数码也未登录。旧 `fusanhe-crm-edge.service`
暂时保留；完成 DNS 切换和缓存期验收后再下线。

已复核当前 Hostinger 的域名列表与 VPS DNS 管理器，仅有
`fshfoodingredients.com`、`fsh.digital`；搜索 CRM 域名没有匹配结果。
公开 RDAP 显示注册商为 Cloud Yuqu LLC（IANA 3824），注册日期
2026-05-08。注册人信息隐藏，尚不能确定实际注册/代理商账号。

回滚材料：美国 `/root/crm-us-migration-20261010/` 保存授权文件、
CRM vhost 和证书；堡垒机同名目录保存旧服务及 known_hosts。
旧服务器公网访问本次超时，不能假设它是可用的回滚入口。

以下内容为原加拿大入口的历史记录。

> 2026-10-09：22005 现已同时承载 CRM、Dify 和渠道采集；22001 Windows 系统已退役。下述 CRM 公网链路保持不变，其他服务入口见 [迁移与运维记录](MIGRATION_22001_TO_22005_2026-10-09.md)。

正式入口：https://gzfusanhesp.com 。HTTP 和 www 跳转到此地址。
DNS 保留加拿大服务器地址，原来跳到独立站的规则已移除。

## 搜索可见性（2026-10-04）

员工控制台固定为 `gzfusanhesp.com`，对外官网固定为
`fshfoodingredients.com`。CRM 根域、www、HTTP/HTTPS 的实际 Nginx
虚拟主机已统一发送 `X-Robots-Tag: noindex, nofollow, nosnippet`，包括
重定向、200、401 和 404 响应。HTTPS `/robots.txt` 在边缘返回允许抓取，
让搜索引擎能读取公开登录页的 noindex；业务 API 继续要求登录。

不要把 CRM robots 改回 `Disallow: /` 来代替退索引，这会阻碍搜索引擎读取
noindex。维护配置时检查 `add_header` 继承，避免新 location 覆盖该响应头。
不要把 CRM 的 noindex 加到官网虚拟主机或共用 WordPress 的全局设置。
官网预览子域 `new.fshfoodingredients.com` 的不收录规则单独限定在该 host。

这次改动保留原有 HTTPS、WebSocket、SSH 转发和鉴权；匿名用户/客户 API
仍返回 401，WebSocket HTTP/1.1 握手为 101。配置备份在加拿大
`/www/backup/seo-rollout-20261004-edge-phase1/`。回滚只恢复此次对应文件，
使用下文实际 Nginx 二进制和主配置校验、重载，不能回滚 CRM 数据。

不收录配置生效与搜索结果更新是两个状态。Google Search Console 的临时移除
需要相应站点权限；截至这次部署未提交移除，不宣称旧搜索结果已消失。
机制依据：[Google noindex 说明](https://developers.google.com/search/docs/crawling-indexing/block-indexing)。

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
