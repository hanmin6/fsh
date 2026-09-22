# 阿里巴巴国际站 Playwright 自动发信服务 (Alibaba Messenger)

基于 Playwright 自动化技术与 FastAPI 构建的阿里巴巴国际站（Alibaba.com）后台消息自动化发送服务。专门用于为独立 CRM 系统提供**日常关怀、节日问候**等自动化发信能力。

---

## 核心特性

1. **持久化免登与首次登录暂停引导**：
   - 基于 Playwright 持久化用户目录（`profile/`），首次启动时若检测到未登录，系统会**自动暂停并弹出可视化浏览器窗口**，醒目提醒你在界面中完成扫码登录；登录完成后自动持久化 Cookie 与 LocalStorage，后续长期免登。
2. **拟人化防风控体系**：
   - 移除 `navigator.webdriver` 等自动化指纹特征；
   - 模拟真人键盘输入，键入间隔随机浮动（20ms ~ 80ms）；
   - 每次发信完毕后执行 3 ~ 6 秒强制冷却，防止频率过高触发风控。
3. **双重防重发保护**：
   - 第一层（API 级）：本地 JSON 流水日志，记录当日已发买家与内容哈希，重复请求毫秒级拦截；
   - 第二层（页面级）：进入会话后校验最新一条我方气泡文本，若内容一致且处于今天则自动跳过。
4. **单浏览器串行排队锁 (`asyncio.Lock`)**：
   - 即使 CRM 并发打入多条请求，服务自动排队依次调度浏览器执行，避免页面操作冲突，超时请求友好返回 `429 QUEUE_TIMEOUT`。
5. **异常自愈与截图留痕**：
   - 遇到元素遮挡或意外异常时，自动截屏存入 `logs/screenshots/`，并在 API 响应中返回截屏路径便于溯源。

---

## 快速上手

### 1. 安装环境依赖
```bash
# 进入项目根目录
cd g:\FSH\alibb

# 安装 Python 依赖
python -m pip install -r alibaba_messenger/requirements.txt

# 安装 Playwright 的 Chromium 浏览器内核（若尚未安装）
python -m playwright install chromium
```

### 2. 启动服务（含首次登录引导）
在终端中直接运行：
```bash
python -m alibaba_messenger.run_server
```

* **初次启动（尚未登录）**：
  * 系统会自动打开带界面的 Chromium 浏览器，并导航至国际站消息中心；
  * 控制台将输出暂停提示：
    ```text
    ======================================================================
    【特别提醒 / LOGIN REQUIRED】检测到阿里国际站账号尚未登录！
    请在已弹出的浏览器窗口中完成扫码登录或账号密码登录。
    登录成功后系统会自动识别并继续...
    ======================================================================
    ```
  * 你只需在弹出的浏览器窗口中完成扫码登录；
  * 登录成功后，系统会自动检测并打印 `>>> 登录成功！会话已就绪 <<<`，同时拉起 FastAPI HTTP 接口。

---

## CRM 接口对接文档

详细完整的生产级对接指南、架构图解、多语言代码示例（Python / Node.js / PHP / Java）及常见问题排查请查阅专用文档：
👉 **[完整 CRM 对接规范文档 (API_DOCUMENTATION.md)](file:///g:/FSH/alibb/alibaba_messenger/API_DOCUMENTATION.md)**

在线交互式文档：
* **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

### 核心接口速查

#### 1. 发送消息 (`POST /api/message/send`)
* **Content-Type**: `application/json`
* **请求体**:
```json
{
  "buyer_name": "Kelvin Tay",               // [必填] 买家姓名 / 旺旺名
  "inquiry_id": "13898396617",              // [推荐] 商机询价单号 (跨页精准定位)
  "message": "Hello Kelvin, hope you are having a great week!", // [必填] 问候内容 (≥10字符)
  "force_send": false,                      // [可选, 默认 false] 是否强制发送(true 则跳过防重拦截)
  "timeout_seconds": 30                     // [可选, 默认 30] 最大排队超时秒数
}
```
* **状态码矩阵**: `200 SENT` (成功), `401 NEED_LOGIN` (未登录), `404 BUYER_NOT_FOUND` (商机未找到), `409 DUPLICATE_IGNORED` (今日已发), `429 QUEUE_TIMEOUT` (排队超时), `500 SEND_FAILED` (执行异常并截图)

#### 2. 服务状态探活 (`GET /api/status`)
* 响应 `data.is_logged_in`: 检测阿里国际站是否登录就绪；`data.waiting_queue_count`: 当前排队任务数。

#### 3. 最近商机会话列表 (`GET /api/conversations`)
* **Query 参数**: `limit` (默认 20), `timeout_seconds` (默认 30)
* 返回商机列表、国旗地区代码、询价单号、创建时间、更新时间、未读计数。

#### 4. 获取商机/买家完整历史记录 (`GET /api/message/history`)
* **Query 参数**:
  * `inquiry_id` (str, 推荐): 商机单号（与 `buyer_name` 二选一）
  * `buyer_name` (str): 买家名称
  * `limit` (int, 默认 0): 获取条数，`0` 为拉取全量会话；`N > 0` 为截取最新 N 条
  * `order` (str, 默认 `"asc"`): 排序规则，`"asc"` 为时间正序从旧到新，`"desc"` 为时间倒序
* 自动向上加载更早历史、深度清洗阿里水印、中英段落分离，正序返回原始单据需求与往来气泡。

## 目录结构说明
```text
alibaba_messenger/
├── config.py                 # 全局配置参数（端口、超时、休眠间隔、CRM 配置）
├── dedup.py                  # 消息防重发校验器
├── alibaba_bot.py            # Playwright 浏览器控制器核心（含会话列表与对话历史解析）
├── crm_gateway.py            # CRM API 网关（安全凭据头、超时与异常分类）
├── outbound_worker.py        # 出向调度 Worker 引擎（心跳上报、Claim 任务拉取、状态流转与发信回写）
├── sync_models.py            # CRM 同步契约标准化模型（Pydantic）
├── sync_service.py           # 历史全量同步编排（分页、分批、重试、断点续传）
├── sync_state.py             # SQLite 断点续传与请求审计记录（不存敏感报文）
├── run_sync.py               # 同步 CLI 操作入口（register / backfill / status）
├── run_worker.py             # 出向发信与心跳守护进程 CLI（claim / sending / result）
├── server.py                 # FastAPI Web API 与并发锁控制
├── run_server.py             # 启动引导主脚本
├── test_api_client.py        # 模拟 CRM 调用的 Python 客户端脚本
├── requirements.txt          # 依赖列表
├── profile/                  # 浏览器持久化目录 (自动生成，保留登录凭据)
└── logs/                     # 日志与截图 (自动生成)
    ├── screenshots/          # 失败时现场截图
    └── sent_records.json     # 防重发流水记录
```

---

## 运行自动化测试
项目中已集成完备的单元测试与端到端同步测试用例，可随时运行验证：
```bash
python -m pytest tests/ -v
```

测试覆盖：
- 消息防重与风控降速（`test_dedup.py`, `test_agent_suite.py`）
- 契约模型与序列哈希（`test_sync_models.py`）
- 状态存储与断点恢复（`test_sync_state.py`）
- CRM 网关通信与异常分类（`test_crm_gateway.py`）
- 历史抓取、气泡排序与非聊天容器过滤（`test_read_messages.py`）
- 基于脱敏 Fixture 的端到端同步与活跃断点跳过（`test_sync_e2e.py`）

---

## 全部询盘导入 CRM（操作指引）

此阶段聚焦在阿里巴巴历史会话/询盘文本只读同步写入 CRM 的统一询盘与 Lead（不进行任何自动外发）：

1. 在隔离的 CRM worktree 启动本地 stack、rebuild 并执行 bootstrap；确认 CRM API 是本机 loopback 地址（如 `http://localhost:18080/api/v1`）。
2. 复制 `.env.example` 为环境配置，填写 `CRM_API_URL`、`FUSANHE_AGENT_KEY` 和账号句柄。切勿将 token、cookie、profile 或 SQLite 状态库提交到 Git。
3. 用一次性 bootstrap 凭据注册/轮换 Agent：`python alibaba_messenger/run_sync.py register --bootstrap <bootstrap>`。命令只显示一次返回 token；立即由人工保存为 `FUSANHE_AGENT_TOKEN`，CLI 不会写盘。
4. 先运行 `python alibaba_messenger/run_sync.py status` 查看断点状态，再运行 `python alibaba_messenger/run_sync.py backfill`。
5. 关键质量保障机制：
   - **防侧边栏污染**：已自动剔除阿里页面侧边挂件文本（如“未读人脉”、“快速锁定主推款”等），确保 `lastMessagePreview` 准确呈现真实买家对话。
   - **时区对齐**：原始北京时间统一由服务端精确归一化存储为标准 UTC，杜绝 8 小时显示漂移。
   - **绝对保序**：消息按 `sourceSequence ASC`（源序列绝对升序）编排入库并在工作台呈现，彻底解决同分钟多气泡排序紊乱。
6. 同一配置再次运行 backfill，已完成的商机会自动跳过断点；可在 CRM 的「AI 客服工作台」(`/#service`) 与「统一询盘」(`/#ExternalConversation`) 中查验完整会话与线索。

默认只允许 loopback CRM URL。连接远程 CRM 必须显式传入 `--allow-remote`，且 URL 必须为 HTTPS；运行前确认目标不是生产环境。

---

## 出向发信与在线心跳守护（Outbound Worker 指引）

Outbound Worker 是阿里执行端与 CRM 任务调度的出向桥接程序，实现 **心跳探活（Heartbeat）+ 任务领取（Claim）+ 发送执行（Send）+ 结果回写（Result）** 的全流程闭环：

### 1. 启动命令
```bash
# 1. 模拟单次试运行（推荐首先运行，验证与 CRM 连通性、心跳上报及 Claim 响应）
python alibaba_messenger/run_worker.py --dry-run --once

# 2. 真实常驻守护进程启动
python alibaba_messenger/run_worker.py --interval 15 --heartbeat-interval 60

# 3. 若需无头模式后台静默运行
python alibaba_messenger/run_worker.py --headless --interval 15
```

### 2. 核心工作机制
- **在线心跳探活 (Heartbeat)**：
  - 启动后立即上报一次心跳，之后默认每 60 秒定期上报 `POST /Fusanhe/agent/heartbeat`。
  - 自动检测阿里网页当前登录态：若正常登录则上报 `status="online"`；若掉线或被阿里风控阻断则上报 `status="offline"` 并携带 `lastError`，促使 CRM 管理后台及时标红预警。
- **任务领取与停发保护 (Claim & Pause Gate)**：
  - 每隔 15 秒向 CRM 发起 `POST /Fusanhe/agent/claim` 领取已由业务员审核通过的发送任务。
  - **停发保护**：若 CRM 端全局保持 `FUSANHE_OUTBOUND_PAUSED=true`，接口返回 `paused: true`，Worker 将自动进入静默冷却，绝不盲目发信或报错崩溃。
- **发送执行与气泡验证 (Send Execution)**：
  - 领取到任务后，首先调用 `POST /Fusanhe/agent/task/:id/sending` 锁定状态。
  - 针对 `executionMode: "mock"` 任务，直接生成模拟回执，不调用真实网页，便于端到端冒烟测试。
  - 针对真实任务，通过 `alibaba_bot.py` 调用 Playwright 模拟真人键入、3~6 秒防风控冷却，并在发送后验证页面出现正文一致的新气泡。
- **结果回写 (Result Reporting)**：
  - 成功发送后调用 `POST /Fusanhe/agent/task/:id/result` 回写平台真实消息时间戳/ID；若发送失败，如实回传错误信息以便 CRM 重试计数或转人工接管。


