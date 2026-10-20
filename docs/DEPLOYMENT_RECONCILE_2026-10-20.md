# 广州部署补齐与公司宽带接入

状态：完整源码已部署并验收，四个 CRM 核心服务健康。公司宽带直连等待网关管理员权限，DNS 保持现状。

## 源码范围

以 main 8918944 为完整基线，补齐 136 个缺失文件及旧源码，包括已登记但缺实现的主动触达证据/客户背调后端。保留现有页面和截图回复功能；四个 JS/CSS 部署产物重建后与 main/当前线上完全一致。

保留主机三份微信晨报修正，并补上同秒并发上下文保护、提交后任何异常保持 uncertain、09:15 后仅恢复已知拒绝的限制。保留获客 CLI 桥接与渠道网关的 recovery supervisor 配置。独立网关的现用生产程序已与 main 一致，保留其状态与部署。

## 验证

- 前端 27 项单元测试、13 项宿主测试通过；TypeScript 与工作台/销售页构建通过，产物无差异。
- 49 项既有离线 Python 契约通过。
- 新增 7 组 report recovery 场景：main 上暴露缺失行为，线上旧补丁上复现 3 个边界问题；修复后全部通过。
- 现有 PHP 策略、微信、晨报、媒体权限、消息翻译、主动触达/背调和截图回复契约通过；自定义 PHP 语法检查通过。所有假 transport 测试在无网络隔离容器执行。媒体跨用户权限检查使用隔离容器 root 执行，生产进程权限未修改。
- 更新前核对 492 个运行源码指纹，无未审阅漂移。

## 数据与回退

生产现有 165 张表；备份和恢复演练结果、最终部署清单/版本及健康状态在本记录末尾追加。备份留在服务器受限目录，数据库、附件、环境文件和平台私有配置不进入 Git。

发生故障时先停止新应用后台任务，恢复旧 release 指针及必要的迁移前数据库/data，再按旧环境文件重建应用并验证，数据库容器和其他知识库栈不重建。保留原 release 和备份；不要使用源码归档覆盖业务数据。

## 公司宽带状态

用户确认域名为 fshcrm.xyz。主机暂无公网 IPv6；默认网关 192.168.1.1 的电信政企网关可达。用户暂时没有网关管理员账号，因此无法核实 WAN、配置 443 转发或完成直连验收。

`deploy/company-broadband/` 提供受 direct profile 控制的 HTTPS 代理配置。启用前要核对公网 WAN、允许的入站端口、适用的电信/备案接入要求和动态地址策略。当前不改变 DNS、不替换公司官网、不开放数据库或共享盘。

下一步所需：由持有公司电信网关管理员权限的人登录，核对公网 WAN 并配置本方案的限定转发。没有管理员权限时不能宣称直连完成。

## 备份记录

完整备份 `/home/fusanhe/fusanhe-crm/backups/reconcile-20261020T004109Z-preflight` 已完成并核验 SHA-256 清单。包括数据库、约 9 GiB 的 Espo data 原始数据、旧 release（含知识资料）、环境文件与网关 supervisor 配置。长任务连接结束后重新核对完成标记及清单，再用于隔离恢复。公司直连 Compose/Caddy 配置均验证通过，但没有启动或开放入口。

## 生产部署验收

当前 release：`/home/fusanhe/fusanhe-crm/releases/reconcile-20261020`。切换前一致性备份：`/home/fusanhe/fusanhe-crm/backups/reconcile-20261020T005845Z-deploy`，包含数据库、完整 Espo data 原始归档、环境文件及表计数，SHA-256 清单通过。

- 1,087 个发布源文件指纹验证通过；四个实际 HTTP JS/CSS 文件与构建产物一致。
- 原有业务记录数量保持一致；新增 outreach_evidence 和 prospect_research 两张表，数据库容器未重建。
- espocrm、daemon、websocket、db 均 healthy；app-check 通过。匿名接口为 401，WAMP WebSocket 握手为 101。
- 原生 Espo 登录、站点/实时连接地址、全局停发与功能开关保留，server.env 字节未变；未向客户发送测试内容。
- `knowledge`、`materials` 链接到旧 release 的原目录，以保留不在 Git 的业务资料。**旧目录 `/home/fusanhe/fusanhe-crm/releases/fad97fc` 仍承载这些资料，不得作为普通旧版本删除。** 新 release 的 `.env` 链接到受限的外部 server.env；没有凭据进入 Git。
- 本机完整 `make verify-offline` 的 Docker fallback 因 Docker daemon 未运行而未执行；49 项 Python 检查已过，其四项 PHP 网关/服务/背调检查均在广州无网络隔离容器逐项通过。其余 PHP 契约和语法、前端测试构建亦通过。

公司宽带直连仍待网关管理员登录、可入站公网 WAN 与运营商接入条件核实；配置已验证，未启动 direct profile、未修改 DNS。当前域名的国内入口备案限制并未因源码更新而解除。

## 独立采集服务的验证边界

渠道采集容器原有 Docker unhealthy 告警仍存在；只读核对显示 Alibaba、MIC、bridge、recovery 及桌面/VNC 等八个 supervisor 进程均 RUNNING。本次保持它们的状态与配置，没有重启或宣称平台登录、采集和全部历史完整性已验收。这个告警不属于四个 CRM 核心容器的健康结果。
