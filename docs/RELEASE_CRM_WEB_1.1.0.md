# CRM Web 1.1.0：双 AI 通道

沿用 crm-web 1.0.0 的统一五页前端。APIMonth 处理文本，TokenDance 处理视频；本次用户明确选择暂不启用静态图片生成。

## 已核实的供应商接口

- GPT-6.1 Sol（gpt-6.1-sol）：Responses。
- Grok 4.7（grok-4.7）、Gemini 3.8 Flash（gemini-3.8-flash）：Chat Completions。
- MiniMax H3 Max（minimax-h3-max）：MiniMax V2 异步视频协议，不能代替图片生成模型。

三种文本模型分别通过虚构小请求；H3 Max 实际完成 5 秒虚构视频并下载 MP4。协议及证据见 [provider-evidence](../specs/006-dual-ai-gateways/provider-evidence.md)。这不代表真实客户或生产环境已验收。

## 配置与升级

服务端配置项见 [.env.example](../.env.example)。密钥仅从环境变量读取。仓库、前端、截图及测试数据均不包含真实密钥。本机用户提供的凭据仅保存在忽略的 `.local/ai-gateways.env`（权限 600），不能复制到 Git 或浏览器。

部署时保留现有数据库/存储卷，用完整服务端环境文件提供数据库、Espo 及 API 凭据。设置 `FUSANHE_TEXT_ENABLED=true` 和 `FUSANHE_MEDIA_ENABLED=true` 后启用相应真实通道；将 `FUSANHE_MEDIA_IMAGE_MODEL` 留空。默认不启用付费媒体调用。旧 AI_* 配置只在新文本通道未启用且无新密钥时保留兼容。

```bash
docker compose --env-file /path/to/server.env up -d
docker compose --env-file /path/to/server.env exec -T espocrm bin/command rebuild
# 在同一完整环境下运行 scripts/bootstrap.py 更新角色权限。
docker compose --env-file /path/to/server.env exec -T espocrm bin/command media-reconcile
```

守护进程必须运行，并完成 bootstrap 注册 Active 的每分钟定时任务。定时任务查询已有任务并保存结果；查询作业不会创建新付费任务。视频链接有时效，应保持后台运行。

## 使用边界

- 推荐方案依据用户手写创作需求；不宣称看过或分析过本地上传的图片。
- 本地原图存入私有服务端空间。图生视频需要用户明确授权公开图片链接；本地文件不会自动公开。无公开链接时可明确选择文生视频。
- 模型输出和费用均须人工核对。费用未知时不显示虚构报价；每日任务数/并发数由服务端限制。
- 提交失败或超时不自动重发。缺少供应商任务号的待核对任务，由管理员从供应商后台核实后恢复查询；管理员可跨所有者恢复编号，但不会获得原图、构想或作品读取权限。
- 新真实回复不传原始客户聊天或内部知识文档，只使用本地匿名话题信号，因此当前侧重谨慎澄清草稿。不能代替完整翻译、产品事实核实或商务承诺审批。
- 生成不自动发送给客户；现有人工审核和全局停发策略继续有效。

## 回退

设置 `FUSANHE_MEDIA_ENABLED=false` 停止新媒体调用；已保存作品和任务保留。停用新文本通道并清空新文本密钥后恢复旧 AI_* 行为。需要代码回退时使用 `crm-web-v1.0.0`，保留数据库与 data 卷；新增表可留存，不删除付费任务证据。不要对待核对任务重新提交。

验收与发布记录见 [verification](../specs/006-dual-ai-gateways/verification.md)。

网络使用 fake-IP 代理 DNS 时，媒体接口会拒绝其保留网段地址。请为供应商及结果域名配置正常公网 DNS/代理绕过，不能关闭私网地址拦截。
