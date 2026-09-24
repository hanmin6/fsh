# Made-in-China (中国制造网) 会话与询盘网关 (MIC Gateway)

MIC Gateway 是面向单一中国制造网 (Made-in-China.com) 供应商账号的本地集成网关，提供订单、询盘、会话历史和受策略约束的 Outbox API。MIC→CRM 的离线桥接已实现；TradeMessenger 全量历史和指定目标身份仍需授权现场验证。当前没有真实发送验收结论。

---

## 🌟 核心特性

- **CRM 集成接口**：标准化 RESTful API，提供订单查询、会话列表、消息历史和发信能力，支持 Python、TypeScript、cURL 对接。
- **可靠发信机制 (Transactional Outbox)**：所有外发消息持久化至 Outbox 队列，经由异步 Worker 进行防重放、重试、限流及结果回执确认。
- **合规风控护栏 (Commercial Policy)**：严格识别报价、议价、PI/订单确认等商业敏感意图，强制触发人工审核，防止非授权承诺。
- **TradeMessenger 适配器**：包含经脱敏契约与离线测试覆盖的页面解析逻辑。只有现场证据能确认会话身份及完整历史后，才可将相应会话用于 CRM 回填或发送。
- **Windows 本地安全架构**：支持交互式登录态保活、本地独立运行时数据隔离（`G:\MadeInChinaGatewayData`），确保凭据与浏览上下文永不泄露至源码库。

---

## 📚 核心文档导航

| 文档 | 描述 | 适用人群 |
| :--- | :--- | :--- |
| **[CRM 开发者对接 API 规范](docs/crm_integration_api.md)** | **涵盖登录态、订单、会话历史、发信、SDK 示例及错误码的完整指南** | **CRM 研发团队、后端集成开发者** |
| **[运维操作与排障手册](docs/operations.md)** | 网关部署、Windows 服务自启、日志审计及异常排查指南 | 运维工程师、系统管理员 |
| **[CRM 桥接配置与验收边界](docs/operations.md#12-mic-to-crm-backfill-and-outbound-worker)** | MIC→CRM 回填、增量同步、Agent 注册和当前现场验收门槛 | CRM 集成与运维人员 |

---

## 🚀 快速上手

### 1. 环境准备

- **操作系统**: Windows 10/11 / Windows Server
- **Python**: 3.11+ 或 3.12+
- **Playwright Chromium**: 用于驱动 TradeMessenger 会话自动化

```powershell
# 1. 创建虚拟环境并激活
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -e .

# 3. 安装 Playwright 浏览器内核
playwright install chromium
```

### 2. 配置环境变量

从模版复制并创建 `.env`：

```powershell
cp .env.example .env
```

核心配置参数说明：

```ini
# 数据隔离目录（必须位于源码树外部）
MIC_APP_DATA_DIR=G:\MadeInChinaGatewayData

# 服务绑定地址与端口
MIC_HOST=127.0.0.1
MIC_PORT=8787

# 同步轮询频率 (秒)
MIC_CONVERSATION_SYNC_SECONDS=30
MIC_ORDER_SYNC_SECONDS=300

# 发送间隔保护 (秒)
MIC_SEND_INTERVAL_SECONDS=10

# 浏览器模式 (生产建议 headless=false 以便交互式维护登录)
MIC_CHROMIUM_HEADLESS=false
```

MIC→CRM 桥接使用 `.env.example` 中的 `MIC_GATEWAY_URL`、`MIC_ACCOUNT_HANDLE`、`MIC_CRM_URL`、`MIC_CRM_AGENT_KEY` 及密钥变量。桥接配置通过进程环境读取，启动 bridge 命令前需在当前 PowerShell 会话或受保护的计划任务环境中设置；不要假定 bridge CLI 会自动读取 `.env`。配置、密钥注册、导入命令和限制详见 [Windows 运维手册](docs/operations.md#12-mic-to-crm-backfill-and-outbound-worker)。

### 3. 初始化与启动网关

```powershell
# Alembic 默认使用相对数据库路径；必须在应用数据目录执行迁移
$sourceRoot = (Get-Location).Path
$env:MIC_APP_DATA_DIR = 'G:\MadeInChinaGatewayData'
New-Item -ItemType Directory -Force $env:MIC_APP_DATA_DIR | Out-Null
Push-Location $env:MIC_APP_DATA_DIR
try {
    & "$sourceRoot\.venv\Scripts\python.exe" -m alembic -c "$sourceRoot\alembic.ini" upgrade head
} finally {
    Pop-Location
}

# 启动生产组合（保持此交互式会话，供专用 Chromium 登录）
.\.venv\Scripts\python.exe -m uvicorn mic_gateway.main:create_production_app --factory --host 127.0.0.1 --port 8787
```

网关启动后，访问健康检查：
```bash
curl http://127.0.0.1:8787/health/live
```

---

## 📡 API 路由概览

所有对接业务端点均挂载于 `/v1`，使用 `X-API-Key` 角色鉴权。详细字段定义与错误码请参考 **[CRM 对接规范文档](docs/crm_integration_api.md)**。

| 业务域 | Method | 端点 | 权限角色 | 核心功能 |
| :--- | :--- | :--- | :--- | :--- |
| **探针与状态** | `GET` | `/health/live` | 无需鉴权 | 服务存活探针 |
| | `GET` | `/health/ready` | 无需鉴权 | 数据库与就绪探针 |
| | `GET` | `/v1/status` | `crm_read` | 网关状态与 MIC 登录态检测 |
| **订单记录** | `GET` | `/v1/orders` | `crm_read` | 获取历史与最新订单记录列表 |
| | `GET` | `/v1/orders/{order_id}` | `crm_read` | 查看单笔订单/询盘详情 |
| **会话历史** | `GET` | `/v1/conversations` | `crm_read` | 获取所有买家会话列表及未读数 |
| | `GET` | `/v1/conversations/{id}/messages` | `crm_read` | 获取指定会话完整消息流水记录 |
| **消息外发** | `POST` | `/v1/conversations/{id}/messages` | `agent_send` | 投递外发消息至 Outbox 队列 |
| | `GET` | `/v1/jobs/{job_id}` | `agent_send` | 轮询发信任务执行与确认状态 |

## MIC → CRM 桥接状态

桥接配置项及运营步骤见 [运维手册第 12 节](docs/operations.md#12-mic-to-crm-backfill-and-outbound-worker)。当前已提供 `register`、`backfill`、`once`、`daemon`、`status` 和 `resolve-pending` 命令；完整历史或会话身份尚未通过现场验收时，导入会失败关闭。出向 Worker 有独立进程入口 `python -m mic_gateway.crm_bridge.run_worker --once/--interval 30`。不得据此宣称 MIC 历史已完整回填或已完成真实发送。

---

## 🧪 自动化测试

运行完整测试套件（含 Contract 测试、集成测试及单元测试）：

```powershell
.\.venv\Scripts\pytest
```

---

## 📂 常用诊断脚本

网关在 `scripts/` 目录下提供了实用诊断和排障工具：

- `scripts/run_live_send.py`：测试端到端向指定买家会话安全发信。
- `scripts/auto_snapshot.py`：自动抓取 TradeMessenger 页面截图与 DOM 树结构并输出报告。
- `scripts/diagnose_chat_ui.py`：实时探测 TradeMessenger 元素并验证回复输入框交互。
