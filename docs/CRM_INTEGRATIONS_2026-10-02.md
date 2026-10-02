# 当前 CRM 接入记录 · 2026-10-02

入口：https://gzfusanhesp.com 。当前生产路径仍采用加拿大 Nginx、堡垒机和公司服务器。

## 已配置并验证

- APIMonth 文本：GPT-6.1 Sol、Grok 4.7、Gemini 3.8 Flash。
  生产服务端状态可读取；供应商 `/models` 已成功返回且包含三个配置 ID。
- TokenDance 视频：minimax-h3-max；供应商目录包含此 ID。
  每日限制 20、并发限制 2，定时查询任务 Active，每分钟执行。
  静态图片生成按此前决定保持关闭。
- 已启用全部现有食品业务 feature flags：商品规格、证书、样品、询价报价、订单。
  重新加载 CRM/daemon/websocket 环境并运行 bootstrap 更新导航、四类角色和定时任务。
  管理员通过公网读取各实体成功，数据库当前为空。
- Muse：专用 `muse-crm-01` Agent 已注册，限定 MuseCRM capability。
  连接器安装在 `/home/fusanhe/fusanhe-crm/integrations/muse_crm_mcp.py`，
  私有凭据在 `/home/fusanhe/fusanhe-crm/private/muse-crm.json`，权限 600。
  初始化、三工具目录、鉴权潜客查询已通过，不创建验收假客户。
  Agent 状态为 offline，明确表示客户端尚未连接，避免虚报在线。
  stdio 连接器不需要启动 HTTP 监听或新增公网端口。

目录验证仅证实网络、API 鉴权和模型 ID，不等于本次已完成模型生成。
本次未提交付费视频或文本请求，也未触发真实平台发送。

## 等待现场信息

用户指定渠道执行端位于堡垒机 `22001` 的福三和 Windows 主机，SSH 用户 `18323`。
现场未发现 8000/8787 抓取监听、Python 抓取进程、渠道计划任务或此前记录中的
`G:\FSH` / `G:\MadeInChinaGatewayData`。18080 是另一套应用，不能作为 CRM 同步目标。
Windows 原平台客户端登录状态不能直接当作专用 Playwright profile 已登录。
因此本次尚未启用渠道同步，也没有迁移历史聊天。待用户确认旧目录或新装后继续。

Muse 的 CRM 服务端和 MCP 连接器已准备好，仍需在实际 Muse Code 客户端加载 stdio
配置；本机未发现 muse/muse-code CLI。不要把服务端工具检查成功描述为 Muse 已获客。
配置方法见 [MUSE_CODE_CRM_MCP.md](MUSE_CODE_CRM_MCP.md)。

## 验证和恢复

`python3 -m unittest discover -s tests -p 'test_muse*.py' -v`：9 项通过。
覆盖 MCP stdio 初始化、范围限制、参数验证、秘密隐藏、重定向限制和写入不自动重试。
生产凭据只存服务器，不进入 Git。

食品模块可通过服务器环境中的各 `FUSANHE_FEATURE_*` 设为 0 并重建三个服务停用。
Muse 可撤销专用 Agent credential 并移除客户端 MCP 配置；保留已有业务记录。
全局渠道停发 `FUSANHE_OUTBOUND_PAUSED=true` 保持开启。
