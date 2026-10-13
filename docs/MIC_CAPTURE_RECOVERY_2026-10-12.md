# 中国制造网抓取恢复

2026-10-12 在 22005 排查并恢复。

登录和来源抓取均正常。CRM 桥接持续报 PendingBatchConflictError。旧入库请求返回 HTTP 409：同一询盘的新快照把询盘 ID 当作备用买家 ID，与原 CRM 身份的真实买家 ID 不同，导致整个同步阻塞。

MadeInChinaSyncService 现在仅在同一渠道账号、同一已绑定会话、旧会话与身份的买家 ID 一致，且输入买家 ID 恰为当前询盘 sourceId 时，保留原买家 ID。真正不同的明确买家 ID 仍返回冲突。不合并客户，不改变身份 key。

隔离的 EspoCRM / MariaDB 测试环境通过 28 项运行及契约检查，涵盖备用标识保留原绑定、重复消息去重、真正身份变化拒绝、发送和草稿无副作用。测试环境随后清理。

线上只部署 MadeInChinaSyncService.php。旧文件备份在 /home/fusanhe/services/outreach/backups/mic-identity-fix-20261012/。桥接数据库备份在执行端 /srv/gateway/backups/mic-identity-fix-20261012/bridge-before.sqlite3。

暂停 bridge，核对旧 requestId 没有成功 AutomationAudit，按 verified-not-accepted 方式解除 pending，保持原 checkpoint，再启动 bridge。没有重启 MIC 和 Alibaba 浏览器。

结果：完整导入核对 12 个会话、115 条消息，actionCodes 为空，pending 为空，checkpoint 为 __mic_import_complete__。12 个会话的既有买家 ID 保持不变。MIC 与 Alibaba 执行端均 online，MIC lastSourceSyncAt 为 2026-10-12 03:42:54 UTC。

两个平台原本已有独立浏览器进程和 profile（/srv/gateway/data/mic/browser-profile 与 /srv/gateway/data/alibaba/profile），共享远程桌面。分开操作窗口方便各自登录，但不解决本次 CRM 批次冲突。
