# 福三和 Windows 抓取端部署 · 2026-10-02

> 2026-10-09 退役说明：渠道抓取已迁至 Linux 22005；Windows 的三个计划任务、`C:\FusanheGateway`、Dify 与 Docker 已按用户要求删除。当前运维见 [22005 迁移记录](MIGRATION_22001_TO_22005_2026-10-09.md)。以下为历史部署记录，不代表当前运行状态，也不能在原目录直接执行恢复命令。

目标：堡垒机 `22001` 的福三和 Windows 11 主机，桌面用户 `18323`。
CRM：<https://gzfusanhesp.com>。

## 2026-10-02 当时状态（历史）

阿里国际站、中国制造网抓取程序已安装；两个 CRM Agent 的独立凭据已通过公网 HTTPS
鉴权。三个计划任务正在运行，设置为 `18323` 登录桌面后自动启动，异常退出一分钟后重启。
平台浏览器均需要首次登录，CRM 中两个 Agent 正确显示 `offline / login_required`。
截至本次验收，ExternalConversation、ExternalMessage、ExternalIdentity 均为 0；没有宣称
完成真实数据抓取或历史迁移。此前导入的历史 Lead 与本次渠道同步是不同业务来源。

在主机的两个专用 Chrome for Testing 窗口中，分别登录阿里国际站和中国制造网。
登录完成后保留窗口；不要用旺旺或 TradeMessenger 桌面客户端的登录状态代替浏览器验证。
MIC 每 30 秒读取平台，两个 CRM 同步循环每 60 秒执行。进入 CRM「消息中心」查看会话；
客户身份会进入现有客户匹配流程。只有成功读取源数据且 CRM 接收后才可验收实际同步。
阿里当前自动循环只扫描最近会话；完整历史回填需要另外执行并逐项验收。

## 版本和目录

基础源码来自 GitHub `hanmin6/fsh` 的 `codex/muse-crm-mcp` 分支，commit `ef7db09`。
该 commit 的两个渠道目录与 GitHub main `364793b` 一致；通过本地 Git archive 传输源码，
无需向 Windows 保存 GitHub 凭据。发布目录还包含本次工作区的以下部署修复：

- 补齐遗漏的 `mic_gateway.runtime.scheduler`，并豁免 `.gitignore` 的 runtime 目录规则。
- MIC 调度器串行执行浏览器操作，登录/验证码暂停工作，浏览器关闭后恢复；支持失败退避、
  手动同步去重和中断关闭；全局停发设置阻止 outbox 执行。
- Alibaba 配置允许数据与 browser profile 存放在源码树外。
- 专用 Windows 入口检查阿里消息页面的正向标记；`login.alibaba.com`、空页、未知页面和
  已关闭窗口不能标为在线。MIC bridge 等待成功的源数据读取才导入，不把空检查点报为成功。

本次修复保存在当前工作区，未执行 GitHub push；部署目录名称表示基础 commit，不表示
其内容没有补丁。重装时必须携带这些修复。

| 用途 | Windows 路径 |
| --- | --- |
| 基础源码与补丁 | `C:\FusanheGateway\releases\ef7db09` |
| Python 3.12.14 | `C:\FusanheGateway\python` |
| 依赖环境 | `C:\FusanheGateway\venv` |
| 私有配置 | `C:\FusanheGateway\private\channels.json` |
| 实际安装依赖清单 | `C:\FusanheGateway\private\installed-requirements.txt` |
| Alibaba profile / SQLite | `C:\FusanheGateway\data\alibaba` |
| MIC profile / SQLite / checkpoint | `C:\FusanheGateway\data\mic` |
| 日志 | `C:\FusanheGateway\logs\alibaba.log`、`mic.log`、`bridge.log` |
| 运行入口 | `C:\FusanheGateway\scripts\run_windows_gateway.py` |

计划任务：`Fusanhe-22001-alibaba`、`Fusanhe-22001-mic`、`Fusanhe-22001-bridge`。
任务直接运行 venv 中的 `pythonw.exe`，避免关闭控制台终止后台进程。任务使用交互桌面
登录类型，因此首次开机尚未登录 `18323` 时不会运行。

目录 ACL 仅授权当前用户、Administrators 和 SYSTEM。平台 profile、真实数据、日志、
CRM token 与 MIC read key 都在受保护目录，不进入 Git。公司 CRM 私有目录保存两个
Agent 的凭据备份；Windows 本地还保存仅供 bridge 使用的 MIC `crm_read` 凭据。
未创建 MIC send/admin key，未启动 CRM outbound worker；全局 `FUSANHE_OUTBOUND_PAUSED=true`。

## 运维

使用这条可用的 SSH 命令。当前 OpenSSH 拒绝原命令的中文/斜杠用户名，裸用户 `18323`
已通过密钥鉴权并确认主机归属：

```sh
ssh -i ~/.ssh/tunnel_operator_ed25519 -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=accept-new -o HostKeyAlias=tunnel-22001 \
  -o 'ProxyCommand=ssh -o BatchMode=yes -W %h:%p root@8.138.165.27' \
  -p 22001 18323@127.0.0.1
```

Windows PowerShell：

```powershell
Get-ScheduledTask -TaskName 'Fusanhe-22001-*' | Select-Object TaskName, State
Get-Content C:\FusanheGateway\logs\alibaba.log -Encoding UTF8 -Tail 30
Get-Content C:\FusanheGateway\logs\mic.log -Encoding UTF8 -Tail 30
Get-Content C:\FusanheGateway\logs\bridge.log -Encoding UTF8 -Tail 30
& C:\FusanheGateway\venv\Scripts\python.exe C:\FusanheGateway\scripts\run_windows_gateway.py status --config C:\FusanheGateway\private\channels.json
```

MIC 仅监听 `127.0.0.1:8787`：`/health/live` 验证进程存活；`/health/ready` 在等待登录时
返回 503；`/v1/status` 必须携带 read key。不要将 503 的等待登录状态当作部署进程缺失，
也不要为了消除 503 改成假健康。没有新增公网监听或修改原 CRM 反向隧道。

更新现有任务的命令（先验证源码和配置，停止期间暂不采集）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\FusanheGateway\scripts\register_windows_gateways.ps1 -UpdateExisting
```

暂停：停止并禁用这三个专用计划任务。若停止任务后仍有其 Python 子进程，确认命令行
指向此运行入口后再按进程树终止；不要终止主机其他 Python、Chrome 或平台客户端。
保留 `data` 与 `private` 目录，可恢复会话与增量检查点。撤销接入时再撤销两个专用 Agent
凭据，不删除客户记录或 CRM 数据卷。

## 验证

在目标 Windows 的 Python 3.12 环境执行 MIC 的 unit/contract/integration，以及 Alibaba
现有测试：MIC 279 passed / 1 skipped，Alibaba 88 passed / 1 skipped，Windows 入口
5 passed。新增测试覆盖登录暂停、手动任务去重、停发仍可采集、浏览器恢复和阿里页面
误判。live/send 测试未执行。任务状态、loopback 监听、公网 Agent 鉴权和等待登录状态
通过实际检查；首次登录后的真实平台读取、CRM 写入和去重验收仍待完成。
