# 阿里国际站与中国制造网 (MIC) 生产服务器部署与会话保活指南

本文档面向系统运维与开发人员，详细阐述阿里巴巴国际站 (`alibaba-client`) 与中国制造网 (`mic-client`) 双通道在生产服务器上的部署配置、会话长效保活 (Keep-Alive)、动态页面自刷新 (Auto-Refresh) 与守护进程管理规范。

---

## 1. 架构总览

两个独立网关均以安全只读增量模式（严格开启 `FUSANHE_OUTBOUND_PAUSED=true`）运行，定期捕获最新会话、历史聊天气泡和买家国家信息，经清洗格式化后推送至本地或内网 EspoCRM。

```
+-------------------------------------------------------------------------------+
|                               生产服务器 (Server)                             |
|                                                                               |
|   +-----------------------+                    +--------------------------+   |
|   |   Alibaba Client      |                    |       MIC Client         |   |
|   |  (Chromium + Daemon)  |                    | (Playwright + Gateway)   |   |
|   |                       |                    |     Port: 8787           |   |
|   |  - keep_alive() 心跳  |                    |  - check_session() 保活  |   |
|   |  - auto_refresh 刷新  |                    |  - 300s 页面自刷新重载   |   |
|   |  - 国家/地区提取      |                    |  - 实时写入 mic.db       |   |
|   +-----------+-----------+                    +------------+-------------+   |
|               |                                             |                 |
|               |                                +------------v-------------+   |
|               |                                |    MIC CRM Bridge Daemon |   |
|               |                                | (自动读取 .env 增量推送) |   |
|               |                                +------------+-------------+   |
|               |                                             |                 |
|               +----------------------+----------------------+                 |
|                                      |                                        |
|                                      v                                        |
|                         POST /api/v1/AlibabaSyncBatch                         |
|                                      |                                        |
|                            +---------v-----------+                            |
|                            |       EspoCRM       |                            |
|                            |   (Port 8080/443)   |                            |
|                            +---------------------+                            |
+-------------------------------------------------------------------------------+
```

---

## 2. 关键保活与自刷新机制 (Keep-Alive & Auto-Refresh)

### 2.1 阿里国际站 (`alibaba-client`)
1. **主动页面刷新 (`auto_refresh=True`)**：
   - 阿里消息中心列表在长期空闲后，WebSocket 容易假死或 DOM 冻结。
   - 守护进程增量轮询 (`run_incremental_once`) 每次发起前均会通过 `bot.get_recent_conversations(auto_refresh=True)` 触发页面重载与 DOM 渲染等待，确保获取到的商机列表永远是服务端最新数据，绝不产生 DOM 盲区。
2. **连接保活与异常自愈 (`keep_alive(force_reload, max_idle_seconds)`)**：
   - 循环检测浏览器是否存活、是否被阿里安全机制重定向到登录页。
   - 自动扫描并关闭可能遮挡界面的营销活动弹窗、升级通知及遮罩层。
   - 检测到掉登时自动将状态置为 `NEED_LOGIN`，防止向失效会话发空请求。
3. **健康巡检与操作接口 (`server.py`)**：
   - `GET /api/health`：提供状态码（UP/DEGRADED）、是否登录、页面 URL 及保活时间戳。
   - `POST /api/session/keepalive`：按需触发保活探测。
   - `POST /api/session/refresh`：在并发互斥锁保护下立即重载商机中心。

### 2.2 中国制造网 (`mic-client`)
1. **空闲连接定时重载 (`MadeInChinaAdapter.check_session`)**：
   - 当浏览器停留在会话页面超过 300 秒（5分钟）时，强制重新导航页面 (`page.goto`)，刷新页面 DOM 并重建 TradeMessenger 长连接。
2. **环境配置零配置装载 (`CrmBridgeConfig.from_env`)**：
   - 桥接进程启动时自动在项目根目录 (`mic-client/.env`) 查找并装载环境变量，无需繁琐的手动导出。
3. **双环调度守护 (`GatewayScheduler`)**：
   - 10 秒健康心跳 (`_health_loop`) 确保登录凭证有效。
   - 30 秒增量会话巡检 (`_conversation_loop`) 同步新询盘及消息到 SQLite，由 Bridge Daemon 推送至 EspoCRM。

---

## 3. 环境变量配置示例

### 3.1 阿里国际站 `alibaba-client/.env`
```ini
# CRM 目标服务配置
FUSANHE_CRM_API_URL=http://127.0.0.1:8080
FUSANHE_AGENT_KEY=alibaba-sync-agent
FUSANHE_AGENT_TOKEN=your_registered_secure_token

# 账号标识与轮询周期
FUSANHE_ACCOUNT_HANDLE=fusanhe_alibaba_main
FUSANHE_SYNC_INTERVAL_SECONDS=60
FUSANHE_SYNC_BATCH_SIZE=50

# 严格安全模式：禁止真实发信
FUSANHE_OUTBOUND_PAUSED=true

# 浏览器行为
HEADLESS=true
```

### 3.2 中国制造网 `mic-client/.env`
```ini
# 数据与配置文件存放路径（必须置于源码树外部）
MIC_APP_DATA_DIR=C:/mic_data

# MIC 网关自身服务
MIC_HOST=127.0.0.1
MIC_PORT=8787
MIC_GATEWAY_URL=http://127.0.0.1:8787
MIC_ACCOUNT_HANDLE=fusanhe_mic_main

# 认证秘钥 (通过 python -m mic_gateway.cli create-key 生成)
MIC_CRM_READ_API_KEY=your_mic_read_key

# CRM 目标端配置
MIC_CRM_URL=http://127.0.0.1:8080
MIC_CRM_AGENT_KEY=mic-sync-agent
MIC_CRM_AGENT_TOKEN=your_registered_mic_token

# 严格安全模式
FUSANHE_OUTBOUND_PAUSED=true
```

---

## 4. 生产服务器运行方案

### 方案 A：使用内置 Python 监督进程 (推荐，跨平台通用)

两个客户端均提供了具备崩溃自动重启、退避重试和信号平滑终止的生产守护脚本：

#### 启动阿里同步守护：
```powershell
# 在 alibaba-client 目录执行
python scripts/run_production_daemon.py --headless
```

#### 启动 MIC 网关与 CRM 桥接：
```powershell
# 在 mic-client 目录执行 (同时拉起 8787 网关与 CRM Bridge)
python scripts/run_production_daemon.py
```

### 方案 B：Windows Server 计划任务 / 开机自启

使用项目附带的 PowerShell 脚本注册交互式登录自启：
```powershell
cd G:\FSH\CRM\fsh\mic-client
powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1 -InstallDir . -Port 8787
```

### 方案 C：Linux Server Systemd 单元配置

针对 Ubuntu / Debian / CentOS 服务器部署：

#### 阿里同步单元 `/etc/systemd/system/fsh-alibaba-sync.service`
```ini
[Unit]
Description=Fusanhe Alibaba Sync Daemon
After=network.target

[Service]
Type=simple
User=fusanhe
WorkingDirectory=/opt/fsh/alibaba-client
ExecStart=/opt/fsh/alibaba-client/.venv/bin/python scripts/run_production_daemon.py --headless
Restart=always
RestartSec=5
Environment=FUSANHE_OUTBOUND_PAUSED=true

[Install]
WantedBy=multi-user.target
```

#### MIC 统一服务单元 `/etc/systemd/system/fsh-mic-gateway.service`
```ini
[Unit]
Description=Fusanhe Made-In-China Gateway & Bridge
After=network.target

[Service]
Type=simple
User=fusanhe
WorkingDirectory=/opt/fsh/mic-client
ExecStart=/opt/fsh/mic-client/.venv/bin/python scripts/run_production_daemon.py
Restart=always
RestartSec=5
Environment=FUSANHE_OUTBOUND_PAUSED=true

[Install]
WantedBy=multi-user.target
```

启动并启用开机启动：
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fsh-alibaba-sync.service
sudo systemctl enable --now fsh-mic-gateway.service
```

---

## 5. 运维监控与故障排查

1. **阿里国际站健康检测**：
   ```bash
   curl http://127.0.0.1:8000/api/health
   # 预期返回: {"status":"UP","data":{"is_logged_in":true,"status":"UP",...}}
   ```
2. **阿里强制会话保活与页面刷新**：
   ```bash
   curl -X POST http://127.0.0.1:8000/api/session/refresh
   ```
3. **MIC 网关健康检测**：
   ```bash
   curl http://127.0.0.1:8787/health
   ```
4. **日志排查**：
   - 阿里日志输出包含 `[Sync] [Incremental]`、`[Daemon] 轮询完成` 及会话更新条数。
   - 遇到 `NEED_LOGIN` 时，终端或控制台会输出清晰提示，提示运维人员扫码或重新认证。
