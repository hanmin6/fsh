# 22005 Linux 渠道抓取部署

这里保存 2026-10-09 从运行中的 `/home/fusanhe/fusanhe-gateway` 核对的公开部署文件。真实配置、平台浏览器 profile、SQLite、同步游标、日志、VNC 密码和 Agent Token 不在仓库内。

运行目录结构：

```text
/home/fusanhe/fusanhe-gateway/
  compose.yaml
  deploy/                       本目录 deploy 中的构建与 supervisor 文件
  releases/<源码提交>/           alibaba-client/ 与 mic-client/
  scripts/run_windows_gateway.py
  private/channels-linux.json   sourceRoot、dataRoot、crmUrl 与私有渠道配置
  private/vnc.pass
  data/                         Linux profile、SQLite 与同步游标
  logs/
```

入口脚本沿用历史文件名 `run_windows_gateway.py`，内部使用跨平台 Python 与 Playwright；Linux 由 supervisor 启动，Windows 注册脚本不参与当前部署。线上 `sourceRoot` 为 `/srv/gateway/releases/ef7db09`，其中包含迁移时的部署修复；发布目录名不能代替源码校验。更新源码需完整保留已应用修复并核对版本。

以下命令在 **22005 的运行目录** 执行，不能直接在仓库模板目录启动生产采集：

```bash
cd /home/fusanhe/fusanhe-gateway
docker compose config --quiet
docker compose ps
docker exec fusanhe-channel-gateway supervisorctl status
```

更新现有部署时先备份配置、状态库和源码，保留 `private`、`data` 与 `logs`，核对私有配置的 `sourceRoot` 与镜像内路径后再构建并切换。`docker compose up -d --no-build` 只用于已有核验镜像，不能用于替代源码发布与浏览器登录验收。

容器使用 host 网络；MIC 8787、noVNC 6080 与 VNC 5901 均绑定 loopback。登录桌面经 SSH 转发访问，见 [迁移与运维记录](../../docs/MIGRATION_22001_TO_22005_2026-10-09.md)。不要把这些端口改成公网监听。

健康检查核验七个 supervisor 进程与 MIC liveness，平台认证和实际采集单独检查。2026-10-09 只读核验时 Alibaba 为 `ready`、MIC 为 `healthy`；这不代替全部历史完整性对账或持续同步观察。CRM 与抓取均保持 `FUSANHE_OUTBOUND_PAUSED=true`，没有启动平台消息发送 worker。

`deploy/runtime-requirements.txt` 为现有镜像的安装依赖锁定记录，不含本地路径或私有索引认证。Dify 的 `deploy.json` / `.env` 含真实密钥，不提交仓库；Dify 继续使用异机备份恢复，不能导入 CRM 数据库。
