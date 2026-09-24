# 实现计划

复用 PHP ServiceKernel、Espo ORM 与原生 ACL；ExternalConversation 增加只读 insights 字段，由服务端 CLI 写入，避免新增实体的独立授权造成泄漏。API `GET /Fusanhe/insights`、`GET /Fusanhe/insights/:id` 仅查询，限制 read=all 或本人名下的记录；详细消息证据需 ExternalMessage 权限。

业务契约由 BossInsightsService / HistorySignals / HistoryAiProvider 负责；客户端仅渲染转义文本和本地实体链接。AI 输入严格为固定词表特征，JSON 结构及证据校验后保存。采用服务器 CLI 的文件锁与单次调用/输出 token 上限，运行统计保存在忽略目录；无重试风暴。新增字段兼容原有记录，分析不触发外发状态机。

覆盖率先保守呈现未知平台总数；不靠已导入数量推断源端总量。新同步报告应包含独立遍历及完整消息验证，未完成保持待对账。

宪章检查：先规格后实现；不发送原文；保留人工控制；端点权限；有针对性测试与运行验证。回退：移除页面入口及路由，保留新增字段以免数据丢失；需要数据库恢复时按 scripts/restore.sh 从此次备份恢复。

验证：make spec-check、make verify-offline、同步契约测试；新增信号/时区/模型输出校验、ACL/分页/只读运行测试；Docker PHP lint、rebuild、app-check。实际账号回填和 20 条抽样独立记录，不能用合成测试替代。

对账补充：服务端 `history-reconcile --file=data/history-manifest.json` 读取执行端的独立源 ID 清单，比较完整会话与消息 ID 集合（不仅数量），保存摘要与文件哈希。仅当源端明确声明分页/历史完整且失败为零、集合相等才显示已全部导入。缺清单显示未知，对账后新同步使结论失效。
