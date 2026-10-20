# Verification

2026-10-20，进行中。Spec/plan/tasks 已通过前置检查；设计审查覆盖所有 FR/SC 与宪章约束，外部直连条件是独立操作门禁。

- 前端：27 unit + 13 native contracts，通过；工作台与 sales TypeScript/Vite build 通过，部署产物与基线完全一致。
- Python：49 个既有离线契约通过。
- PHP 新增 recovery fixture：main 失败 6 组，原生产补丁失败 3 组；修复后 7/7 通过。验证拒绝分类、新鲜上下文、两次重试上限、终态不重发、显式 legacy diagnosis、同秒并发的三个轮询入口、晚发边界和内部字段过滤。
- 已有 PHP 策略/权限/渠道/晨报/媒体/翻译/背调/截图回复契约通过；全 custom PHP lint 通过。无网络隔离测试，未发送真实消息或调用 provider。
- 生产源码 preflight：492 个运行文件指纹无漂移。
- 正式部署已通过下述验收；外部直连仍待路由器/公网接入条件，未计为完成。

- 隔离恢复验收通过：165 → 167 张表，新增 outreach_evidence/prospect_research；重建前后已有业务记录数量一致。七项 HTTP/无外发检查通过：匿名拒绝、证据创建与同请求回放、修改回放冲突、列表、JSON data URL 图片哈希、普通无权限用户拒绝、无新增发送任务。全程使用 Docker internal 网络、禁用 provider、未启动 daemon。首次测试容器只读自定义目录与 Espo 初始化 chown 不兼容，已使用与生产一致的可写自定义目录；截图测试已纠正为既有 JSON data URL 契约。

- 生产切换通过：一致性备份清单有效，1087 个源文件指纹一致，两个表补齐且原业务计数不变；数据库容器保持原 ID，四核心容器 healthy，HTTP 静态产物一致，匿名 401，WAMP 握手 101，环境文件未改。
- 本机 `make verify-offline` 跑过 49 项 Python 检查后在 Docker fallback 受本机 daemon 缺失限制；四项 PHP fallback 检查在服务器隔离容器逐项通过，不将本机整体 Make 记为通过。
- Direct Compose 与 Caddy validate 通过。用户确认域名 fshcrm.xyz，但暂时没有公司电信网关管理员账号；WAN、端口转发、运营商接入条件及外部 HTTPS 验收待完成。
