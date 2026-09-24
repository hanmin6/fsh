# Made-in-China CRM 接入架构计划

关联需求：[spec.md](spec.md)。详细执行步骤见 [实施计划](../../docs/superpowers/plans/2026-09-23-made-in-china-crm-integration.md)。

## 方案选择

推荐保持 `G:\FSH\made-in-china\made-in-china` 为独立平台网关：网关负责浏览器、同步缓存和 Outbox；新增独立 MIC→CRM 桥接程序，以 MIC 网关只读 API 做历史回填与增量同步，以 CRM Agent API 领取获批任务，并调用网关发信 API。CRM 新增 MIC 入库契约，复用现有身份、Lead、会话和审批状态机。

备选方案为 CRM 定时直接拉网关 API，代价是把渠道凭据和断点调度放进 PHP 服务；另一方案是复制网关进入 CRM 仓库，代价是浏览器部署与 CRM 发布耦合。推荐方案与 Alibaba 的 Agent 边界一致，也保留 MIC Outbox 的发送确认能力。

## 契约与兼容

- `G:\FSH\made-in-china\made-in-china` 拥有 `/v1/conversations`、`/v1/conversations/{id}/messages`、`/v1/conversations/{id}/messages` POST 及 `/v1/jobs/{id}` 的版本化契约。
- `G:\FSH\CRM\fsh` 拥有新 `/Fusanhe/mic/sync`、Agent 领取/发送/结果与 CRM 实体契约。
- CRM 的会话唯一键是 `(MadeInChina channel/account, MIC source_id)`，买家身份键是 `(MadeInChina, accountHandle, buyer_reference)`；网关 UUID 只用于网关请求，不代替平台源 ID。
- MIC 同步报文保留 `sourceSequence`、`externalId`、`direction`、`messageType`、源时间及时间可信度。未知姓名使用可识别的临时名称，后续只升级临时资料，不覆盖人工修改。
- 现有 Alibaba 端点、任务契约与数据保持兼容。新 MIC Agent 只注册 `MadeInChina` capability。

## 数据流

MIC 授权浏览器 → 网关 SQLite → 桥接程序断点扫描 → CRM `/Fusanhe/mic/sync` → 身份/Lead/会话/消息；CRM 审批 → MIC Agent 领取任务 → MIC 网关 Outbox → 平台确认 → Agent 回写 CRM。历史回填只读且无自动外发副作用。

## 风险与回退

当前 MIC 网关只验证了询盘列表与初始询盘正文；TradeMessenger 在发现时出现初始化失败。本机保存的页面快照证明双向气泡、发送方/时间节点和历史加载控件存在，但未证明历史翻页与源消息 ID。可基于已观察结构和合成夹具推进离线代码；必须以授权账号完成只读契约发现，证明能够取得完整双向历史后再声称 MIC-01 完成或进入真实发布。页面不可用时保持导入断点和停发，人工处理登录或页面问题，不绕过平台验证。功能回退为停止 MIC 桥接与 Agent、保持全局停发；已导入 CRM 记录保留供审计，不自动删除。

## 项目宪章检查

规格先于代码；外发逐条人工批准；接口、幂等与状态转换有契约测试；运行时验证后才标完成；凭据和买家资料不进入 Git；停发、失败和回退路径可审计。
