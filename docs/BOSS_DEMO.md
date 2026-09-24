# 老板历史客户演示

## 入口
本机演示库：`http://localhost:8080/#Home/insights`。首页“历史客户与今日建议”也可进入。
独立验收库：`http://localhost:18082/#Home/insights`；此库仅有明确标记的合成测试数据，不能作为真实客户演示。

## 演示顺序
1. 老板只读账号登录，查看全局停发提示。
2. 看平台可见、已导入、同步失败、身份待确认、分析完成/失败/过期，以及最后同步时间。未知为“待核对”或“未知”，不能口头宣称全部完成。
3. 搜索客户会话名称或平台稳定 ID；同名记录以 ID 区分，打开 CRM 客户和原始会话。
4. 点“查看分析”，核对匿名信号摘要、需求、历史进展、最新状态、缺失事实和证据消息链接。产品/具体商务事实不足时保持待确认。
5. 看上海当日建议与负责人；原文核对和下一步由人工执行。页面没有发送或生成草稿入口。

## 后台分析
先备份并 rebuild；实际导入和对账后，从受控服务器执行：

```sh
docker compose exec -T espocrm bin/command history-analyze --limit=5
# 失败重试需显式指定；相同版本成功结果命中缓存。
docker compose exec -T espocrm bin/command history-analyze --limit=5 --retry
```

单次最多 100 次调用，每上海自然日硬上限 100 次，每次最多 900 输出 tokens。预算在请求前预留，进程中断也计费预算；文件锁防止同实例并发。`data/history-analysis-budget.json` 保存当天预留次数；不要为了重复尝试而清空预算。模型失败不降级成 Mock。

模型只收到固定类别词表（询价、样品、规格、交期、认证）及次数/方向/匿名编号，不收到姓名、联系方式、平台 ID、原始消息或附件。所有源消息在本地按 200 条一段流式归纳并哈希，模型输入最多 21 条词表证据。

## 独立对账
在采集端完整分页并确认每个会话历史加载完整后，生成私密 JSON 清单，只包含平台 ID，不放客户正文。结构：

```json
{"accountHandle":"账号标识","enumerationComplete":true,"historyComplete":true,"failed":0,"conversations":[{"id":"会话稳定ID","messageIds":["消息稳定ID"]}]}
```

`enumerationComplete` / `historyComplete` 必须有源页面验证依据，不可因循环退出或最近会话列表返回成功就填 true。将该私密文件放进服务器 `data/history-manifest.json`，执行：

```sh
docker compose exec -T espocrm bin/command history-reconcile --file=data/history-manifest.json
```

服务端逐项核对会话和消息 ID 集合；失败、少记录、多记录、不完整消息均不会显示全部完成。数据库仅保存计数、差异结论、时间及清单哈希；原始清单不提交 Git。对账后有新同步须重新核对。

## 2026-09-24 当前真实状态
- 演示库真实历史导入 0；身份待确认 0；分析完成/失败 0；建议 0。平台可见数与源端失败数尚未获取，不能视作零。
- 已连接用户指定的“福三和——主机”；已有 Alibaba OAuth 桥接状态 healthy / connected，授权未过期。OAuth 有效不等于历史消息读取已可用。
- 主机未发现正在运行的 Python 采集服务；常见项目路径未找到 run_sync.py；可找到 Python 3.11，但该环境未安装 Playwright。未修改主机浏览器登录态，也未安装或启动外发服务。需确认用户实际登录入口后接入。
- 业务模型：`https://modcon.top/v1`，`gpt-5.6-luna`，已验证 JSON 输出。两次测试分别消耗 692 和 620 tokens，合计 1312；中转实际价格未核实，金额未知。真实客户批量分析尚未调用。
- 现有数据库和应用数据备份：`backups/20260923-233042/`。回退前参照 `scripts/restore.sh`，不要直接删除生产卷。

## 尚未完成的验收
真实账号全历史回填、平台完整分页/消息 ID 清单、20 个真实客户首尾消息与方向时区抽查、真实画像效果评估和费用确认。当前交付的画像是匿名规则信号分析，不能覆盖原文级完整需求/产品理解。
