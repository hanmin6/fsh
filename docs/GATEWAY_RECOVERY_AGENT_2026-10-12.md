# 平台同步与登录恢复 agent

2026-10-12 部署到 22005。执行端为 fusanhe-channel-gateway，CRM 为 crm.fsh.digital。

## 运行方式

Supervisor 的 recovery 服务每 60 秒检查 mic、bridge、alibaba。连续两次异常才请求 CRM 现有 TextGateway，通过 APIMonth 调用 gpt-6.1-sol；实际模型响应已核对。模型只接收结构化运行状态，不接收密码、客户消息、网页或原始日志。账号与采集器均有单独的 capability 范围。

允许的恢复动作包括：恢复停止的指定采集进程、调用保存密码登录、重新抓取、重放保留的原始同步批次。执行前重新检查状态，抓取正在运行时不打断。每个 worker 每小时最多 4 次恢复操作，操作之间至少 300 秒；这是防止登录/重启循环的保护，不是获客数量限制。

模型不能直接写生产代码或执行任意 shell。未知身份冲突、缺失原始批次、验证码、短信验证、未接受的条款和无法确认的登录转人工。相同阻塞状态不重复尝试。

## 登录流程

MIC 的英文 /logon.do 是买家入口。自动恢复进入同域供应商 /sign-in/ 页面，并指定 switchLan=1，保留的返回地址只允许 membercenter.made-in-china.com。需要时选择“密码登录”。

浏览器使用独立的 MIC / Alibaba profile。恢复代码只检查字段是否已填入，等待 Chromium 原生自动填充生效，必要时通过账号输入框调用保存账号，再确认密码框。不会读取 input_value、解密 Login Data 或把密码放入日志/模型。提交登录后，必须实际回到已认证消息页并恢复来源同步，才记录 healthy_verified。

Alibaba 启动等待登录时会覆盖旧进程的 browser-status.json，避免旧的 ready 状态使模型误判会话健康。

## 同步批次恢复

CRM bridge 的 SQLite journal 继续记录批次哈希、请求 ID 与游标。另在私有 pending-replay 目录临时保留原始请求，目录 0700、文件 0600；入库确认后删除。重放必须使用同一请求 ID、同一原始内容，并核对哈希。先查 CRM 成功审计，没有审计表示 not_confirmed，不推断已经拒绝或已经成功。旧批次缺少原始内容时转人工。

重放前只暂停 bridge，备份 journal；浏览器不重启。正常入库时短暂存在的 pending 不被视为冲突；仅明确冲突、失败、停止或长期没有成功同步时触发恢复。先处理旧 pending，确认后才读取新快照。保留 MIC 买家身份回退修复，不覆盖已有真实买家绑定。

## 部署与回滚

- 执行端脚本：/srv/gateway/scripts/gateway_recovery_agent.py、gateway_recovery_login.py、run_windows_gateway.py。
- 私有配置：/srv/gateway/private/recovery-agent.json；模型密钥仍在 CRM。
- 状态与动作结果：/srv/gateway/data/recovery/，保留最近 100 条事件。
- 持久 supervisor 配置：/srv/gateway/deploy/supervisord.conf。
- 发布目录：/home/fusanhe/services/outreach/releases/recovery-agent-20261012。
- 执行端备份：/srv/gateway/backups/recovery-agent-20261012。
- CRM 路由备份：/home/fusanhe/services/outreach/backups/recovery-agent-20261012/routes-before.json。

回滚先停止 recovery，恢复备份源文件与 supervisor 配置，将私有 channels 配置的 recoveryEnabled 设为 false，再按需逐个重启采集器。CRM 当前路由包含其他功能修改，应只移除恢复路由，不能用旧 routes 整体覆盖。

## 验证

隔离源目录 /srv/gateway/validation-recovery-20261012 中通过 52 项 Python 检查，覆盖过期/错账号命令、密码只读布尔状态、延迟原生自动填充、MIC 供应商入口、恢复后清除旧命令状态、批次重放与 scheduler。之后针对正常入库不误判为失败的补丁通过 13 项 recovery 检查，Alibaba 启动状态修复通过 6 项 gateway 检查。PHP scope / action allowlist / audit result 契约与语法检查通过。

现场已验证 MIC 和 Alibaba 在登录失效后，由模型选择 auto_login、浏览器保存密码填入并提交，自动返回各自消息中心。MIC bridge 已重新确认 12 个会话、115 条消息，actionCodes 为空。线上来源、agent 进程与 CRM 展示的最终验收快照见 deployments/outreach-22005/records/recovery-acceptance-20261012.json。

本次验证未创建或发送测试客户消息，原有获客规则及接待规则保持既有配置。

## 2026-10-13 恢复监控补强

现场发现恢复程序曾反复选择 wait，随后转 needs_human。source_sync_pending_or_failed 被映射为 source_stale，但服务端动作仅按 CRM 成功时间是否超过 1800 秒允许 retry_sync；源异常而 CRM 时间尚较新时没有可重试动作。实际采集器还能因未结束的响应处理长期占用共享浏览器锁，恢复命令也无法及时消费。

采集器已修正 React 会话标识加载等待、取消未完成的多余响应处理、调度操作超时与私有 poller 诊断；完整 12 会话已实测成功且下一轮启动，见根目录中国制造抓取修复记录。

恢复 agent 现在同时核对平台源会话成功时间和 CRM 成功时间，取较旧者。正在失败的检查点不再算作 busy；使用私有 poller 诊断识别正在运行的完整采集。必要任务缺失，或持锁且消息/会话连续 900 秒没有成功进展时，报告 worker_unresponsive，允许限定采集器重启。源已明确异常时允许空闲采集器 retry_sync，不依赖 CRM 时间先过期。

普通登录正常但重试命令超过 300 秒未消费且采集器空闲时，按原每小时最多 4 次限制直接重启指定 worker，不将普通卡死永久标成待人工。验证码、来源身份冲突、原始批次缺失和不明错误仍停止并保留人工处理，不允许模型自行修改生产代码或客户关系。

本次部署仅重启 recovery，保留 MIC/Alibaba/bridge 运行与登录。Python 恢复/调度/状态相关测试 26 项通过，恢复策略和服务权限 PHP 契约通过，已验证 recovery、mic、bridge、alibaba 均运行并报告健康观测。备份 `/home/fusanhe/fusanhe-gateway/backups/recovery-watchdog-20261013-093911`。
