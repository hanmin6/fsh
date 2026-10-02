# 历史客户资料导入记录

2026-10-02 已向生产 CRM 导入共享盘中核实的 3 位潜在客户、4 份源文件（2 份 Word 文稿、2 份客户专属报价）。同一客户的两份报价合并到一个 Lead；公司与买方联系方式未提供时留空，未评级，状态为 New。

查看位置：网页版「客户与评级」→「客户类型」选择「潜在客户」。客户概览保存需求摘要、原文和来源路径；原件存放在该 Lead 的原生动态 Note 附件中。

没有将历史回复文稿标为已发送消息，没有创建确认订单，也没有启用外发。加拿大旧会话系统历史表为空；独立站发现的记录均为测试数据，排除。共享盘中的运营模板、通用报价和卖方联系方式不作为买方数据导入。本次不是完整平台会话历史迁移。

导入前备份：`/home/fusanhe/fusanhe-crm/backups/crm-before-history-import-20261002.sql`。
私有清单及执行脚本保存在服务器 `private/history-import/`；本地源文件和清单保存在被 Git 忽略的 `.local/history-import/`。实际客户资料及 API 凭证不进入 Git。

复用 `scripts/import_history.py`：在私有 JSON 清单中为每个客户指定稳定 `key`、审核后的 `lead` 字段，以及含 `name`、`type`、`base64` 的 `documents`。配置 `ESPOCRM_API_URL`、`ESPOCRM_ADMIN_USERNAME`、`ESPOCRM_ADMIN_PASSWORD` 环境变量，先运行不带 `--apply` 的校验，再在备份后使用 `--apply` 导入。保持单实例执行；相同来源标记不覆盖现有资料，重复运行不新增客户或已关联附件。

验收：生产 API 确认总计 3 个 Lead，买方邮箱/电话均为空；原文、国家与清单一致；4 份下载附件的 SHA-256 与源文件一致；第二次导入新增数为 0，附件数仍为 4；外发暂停设置保持为 true。
