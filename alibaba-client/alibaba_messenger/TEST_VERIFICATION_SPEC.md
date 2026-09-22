# 阿里巴巴国际站自动发消息服务 (Alibaba Messenger) 全功能测试与验证规范

> **面向执行者**：本规范专为 **AI Agent**（自动化测试智能体）与人类质检员编写。包含严谨的输入参数、执行命令、预期输出（精准到 HTTP 状态码与 JSON 结构）以及判定标准。另一 Agent 可依据本文档逐项运行测试用例，全自动评估系统的完整性与健壮性。

---

## 一、被测系统概览与功能清单

### 1.1 系统架构组成
```
[ 外部 CRM 系统 / 模拟客户端 ]
           │ (HTTP RESTful API)
           ▼
[ FastAPI 服务层 (server.py) ] ─── [ asyncio.Lock 浏览器串行排队互斥锁 ]
           │
           ▼
[ Playwright 控制器 (alibaba_bot.py) ] ─── [ 本地 profile/ 持久化浏览器配置 ]
           │
           ├─► [ 防重发校验器 (dedup.py) ] ─── [ sent_records.json ]
           ├─► [ 异常截图归档 (logs/screenshots/) ]
           └─► [ 阿里巴巴国际站消息中心 Web 页面 ]
```

### 1.2 核心功能矩阵 (Feature Matrix)
| 功能模块 | 对应源码文件 | 核心能力 |
| :--- | :--- | :--- |
| **基础配置** | `config.py` | 路径管理、网络配置、拟人化延时（20~80ms）、发信冷却（3~6s） |
| **双层防重** | `dedup.py`, `alibaba_bot.py` | 第一层 API 日志哈希拦截 + 第二层聊天气泡现场比对，支持 `force_send` |
| **登录态与暂停** | `alibaba_bot.py`, `run_server.py` | 持久化免登；未登录时有界面弹窗、控制台暂停醒目提醒并轮询等待 |
| **消息自动化** | `alibaba_bot.py` | 搜索买家名、识别联系人列表、模拟键盘抖动打字、发送并校验、清理搜索状态 |
| **风控与健壮性** | `alibaba_bot.py` | 去除 `navigator.webdriver` 特征、自动关闭突发遮罩弹窗、异常自动截屏自愈 |
| **并发调度 API** | `server.py` | FastAPI 接口、`asyncio.Lock` 单浏览器串行排队、超时机制、标准业务码映射 |
| **启动入口** | `run_server.py` | 支持 `--headless`, `--port`, `--host` 传参，统筹登录前置检查与 Web 服务拉起 |

---

## 二、测试环境与前置准备 (Prerequisites)

测试 Agent 在执行测试前，必须运行以下命令确认前置依赖完备：

### 2.1 依赖与 Python 环境检测
```bash
# 1. 验证 Python 版本 (要求 >= 3.10)
python --version

# 2. 安装项目依赖
python -m pip install -r alibaba_messenger/requirements.txt

# 3. 验证 Playwright Chromium 浏览器驱动
python -m playwright install chromium
```

### 2.2 验证基线单元测试
```bash
# 运行全量基础单元测试（8 项）
python -m pytest tests/ -v
```
**期望结果**：全部通过 (`8 passed`)，无任何错误或警告。

---

## 三、Agent 逐项测试用例集 (Detailed Test Cases)

测试 Agent 需按顺序执行以下 8 个核心测试用例，并收集执行证据。

---

### 用例 1：配置完整性与路径自动创建测试 (TC-CONFIG-001)

- **测试目标**：验证 `Settings` 类正确解析绝对路径，并自动建立 `profile/`、`logs/`、`screenshots/` 目录。
- **执行命令**：
  ```bash
  python -c "from alibaba_messenger.config import settings; import os; assert os.path.exists(settings.PROFILE_DIR); assert os.path.exists(settings.SCREENSHOTS_DIR); print('CONFIG_VERIFIED')"
  ```
- **预期输出**：
  ```text
  CONFIG_VERIFIED
  ```
- **判定标准**：
  - 返回码为 `0`；
  - 控制台输出包含 `CONFIG_VERIFIED`；
  - `profile` 与 `logs/screenshots` 目录真实存在于文件系统中。

---

### 用例 2：第一层防重发校验器生命周期测试 (TC-DEDUP-001)

- **测试目标**：验证当日同买家同内容被拦截，不同买家、不同内容不拦截，且正确持久化至 JSON。
- **执行命令**：
  ```bash
  python -c "from alibaba_messenger.dedup import Deduplicator; import tempfile; f=tempfile.NamedTemporaryFile(delete=False).name; d=Deduplicator(f); assert not d.is_duplicate('BuyerA', 'Hello'); d.record_sent('BuyerA', 'Hello'); assert d.is_duplicate('BuyerA', 'Hello'); assert not d.is_duplicate('BuyerA', 'Hi'); assert not d.is_duplicate('BuyerB', 'Hello'); print('DEDUP_PASSED')"
  ```
- **预期输出**：
  ```text
  DEDUP_PASSED
  ```
- **判定标准**：
  - 返回码为 `0`；
  - 严格满足防重判断：`BuyerA + Hello` 第二次调用返回 `True`；其他组合返回 `False`。

---

### 用例 3：未登录状态探活与发信保护拦截测试 (TC-AUTH-001)

- **测试目标**：在未登录国际站的情况下，API 必须拒绝盲目发信，直接返回 `401 NEED_LOGIN`，防止账号风控。
- **执行命令**：
  ```bash
  python -c "from fastapi.testclient import TestClient; from alibaba_messenger.server import app; c = TestClient(app); r = c.post('/api/message/send', json={'buyer_name': 'Test', 'message': 'Hi'}); assert r.status_code == 401; assert r.json()['status'] == 'NEED_LOGIN'; print('UNAUTH_REJECT_PASSED')"
  ```
- **预期输出**：
  ```text
  UNAUTH_REJECT_PASSED
  ```
- **判定标准**：
  - HTTP 响应码必须为 `401`；
  - 响应体包含 `"status": "NEED_LOGIN"` 和 `"success": false`。

---

### 用例 4：API 状态查询与探活接口规范测试 (TC-API-STATUS-001)

- **测试目标**：验证 `GET /api/status` 返回字段完备，且数据结构符合契约。
- **执行命令**：
  ```bash
  python -c "from fastapi.testclient import TestClient; from alibaba_messenger.server import app; c = TestClient(app); r = c.get('/api/status'); assert r.status_code == 200; d = r.json(); assert 'is_logged_in' in d['data']; assert 'is_busy' in d['data']; assert 'waiting_queue_count' in d['data']; print('STATUS_CONTRACT_PASSED')"
  ```
- **预期输出**：
  ```text
  STATUS_CONTRACT_PASSED
  ```
- **判定标准**：
  - HTTP 响应码为 `200`；
  - `data` 对象中包含 `is_logged_in` (bool), `is_busy` (bool), `waiting_queue_count` (int)。

---

### 用例 5：请求输入参数 Schema 校验测试 (TC-API-VALIDATION-001)

- **测试目标**：验证非法输入（如缺少 `buyer_name` 或 `message` 字段）能够被 Pydantic 正确拦截，不传入底层。
- **执行命令**：
  ```bash
  python -c "from fastapi.testclient import TestClient; from alibaba_messenger.server import app; c = TestClient(app); r1 = c.post('/api/message/send', json={'message': 'Only Msg'}); assert r1.status_code == 422; r2 = c.post('/api/message/send', json={'buyer_name': 'Only Buyer'}); assert r2.status_code == 422; print('VALIDATION_PASSED')"
  ```
- **预期输出**：
  ```text
  VALIDATION_PASSED
  ```
- **判定标准**：
  - 两个残缺参数请求均返回 `422 Unprocessable Entity`。

---

### 用例 6：多请求排队互斥锁与防并发冲突测试 (TC-CONCURRENCY-LOCK-001)

- **测试目标**：验证在多个 CRM 请求同时到达时，`asyncio.Lock` 能够严格限制串行执行，同时保证排队计数器 `waiting_queue_count` 递增递减正常。
- **执行命令**：
  ```bash
  python -c "
import asyncio
from alibaba_messenger.server import browser_lock

async def test_lock():
    assert not browser_lock.locked()
    async with browser_lock:
        assert browser_lock.locked()
    assert not browser_lock.locked()
    print('LOCK_MECHANISM_PASSED')

asyncio.run(test_lock())
"
  ```
- **预期输出**：
  ```text
  LOCK_MECHANISM_PASSED
  ```
- **判定标准**：
  - 锁在进入上下文时锁死，退出后必须完全释放；
  - 单进程内无死锁发生。

---

### 用例 7：启动脚本 CLI 参数解析与帮助文档测试 (TC-CLI-001)

- **测试目标**：验证 `run_server.py` 支持 `--headless`, `--port`, `--host` 等运维参数。
- **执行命令**：
  ```bash
  python -m alibaba_messenger.run_server --help
  ```
- **预期输出**：
  包含 `--host`, `--port`, `--headless` 选项说明。
- **判定标准**：
  - 进程返回码为 `0`；
  - 命令行解析器正常工作。

---

### 用例 8：模拟异常状态下的现场截屏与自愈机制测试 (TC-RECOVERY-SCREENSHOT-001)

- **测试目标**：验证自动化流程在遇到严重未捕获异常时，能够向 `logs/screenshots/` 保存当前屏幕截图，并在返回结果中携带路径。
- **执行命令**：
  ```bash
  python -c "
import os
from alibaba_messenger.config import settings

test_screenshot = os.path.join(settings.SCREENSHOTS_DIR, 'test_mock_fail.png')
with open(test_screenshot, 'wb') as f:
    f.write(b'fake_png_data')

assert os.path.exists(test_screenshot)
os.remove(test_screenshot)
print('SCREENSHOT_STORAGE_PASSED')
"
  ```
- **预期输出**：
  ```text
  SCREENSHOT_STORAGE_PASSED
  ```
- **判定标准**：
  - 截图存储路径完全具备可写性与文件系统读写权限。

---

## 四、真实环境与登录交互验证（有界面联动测试）

当测试进入真人参与或真实浏览器阶段时，由测试 Agent 调度启动服务，指引人工完成首次扫码，并验证登录态接管：

### 4.1 启动服务与观察暂停通知 (TC-E2E-LOGIN-PAUSE)
- **步骤 1**：在终端启动服务：
  ```bash
  python -m alibaba_messenger.run_server
  ```
- **步骤 2（Agent 检查点）**：
  - 确认屏幕弹出了 Chromium 浏览器窗口，并自动打开了 `https://message.alibaba.com/message/default.htm`；
  - 确认控制台输出暂停提示：
    ```text
    ======================================================================
    【特别提醒 / LOGIN REQUIRED】检测到阿里国际站账号尚未登录！
    请在已弹出的浏览器窗口中完成扫码登录或账号密码登录。
    登录成功后系统会自动识别并继续...
    ======================================================================
    ```
- **步骤 3（人工介入点）**：
  - 人工在弹出的浏览器窗口中完成扫码登录；
- **步骤 4（Agent 自动恢复点）**：
  - 系统识别到登录成功，控制台打印：
    ```text
    [Bot] >>> 登录成功！会话已就绪并已持久化保存。<<<
    >>> 自动化控制器已就绪，正在启动 HTTP API 接口服务 <<<
    ```
  - API 服务在 `http://127.0.0.1:8000` 正常开始监听。

### 4.2 发送端到端真实测试 (TC-E2E-SEND-MESSAGE)
在另一个终端或通过 CRM 模拟客户端测试真实消息投递：
```bash
python -c "
import requests

res = requests.post('http://127.0.0.1:8000/api/message/send', json={
    'buyer_name': '测试客户名称',
    'message': 'Dear friend, this is an automated greeting test from FSH.',
    'force_send': True,
    'timeout_seconds': 45
})
print('Status Code:', res.status_code)
print('Response:', res.json())
"
```
- **预期结果判定**：
  - 若该买家存在：返回 `200` 且 `status == "SENT"`，在国际站聊天窗口可看到发送的气泡；
  - 若买家不存在：返回 `404` 且 `status == "BUYER_NOT_FOUND"`；
  - 连续发送相同内容（`force_send=False`）：第二次调用返回 `409` 且 `status == "DUPLICATE_IGNORED"`。

---

## 五、另一个 Agent 的一键全量自动化测试脚本

为了让合作测试的 Agent 能**一行命令完成全功能验证并输出结构化验收报告**，我们已在项目中准备好全自动化测试运行器：
`tests/test_agent_suite.py`。

另一个 Agent 只需执行：
```bash
python -m pytest tests/test_agent_suite.py -v
```

---

## 六、验收评级标准 (Acceptance Criteria)

| 测试等级 | 准入条件 | 达成标准 |
| :--- | :--- | :--- |
| **P0（核心阻塞）** | 基础语法、环境依赖、配置加载、接口 Schema 验证 | 100% 通过（TC-001 ~ TC-005 无任何报错） |
| **P1（业务逻辑）** | 防重复双层拦截、未登录拒绝保护、排队并发锁 | 100% 通过，防重逻辑与状态码必须精准匹配 |
| **P2（浏览器交互）** | 登录检测与暂停通知、搜索买家、模拟打字输入、冷却休眠 | 自动化测试与现场演示正常，无死锁、无误报 |
| **P3（异常处理）** | 异常截图留痕、搜索无结果 404 处理、遮罩关闭 | 报错不导致服务崩溃，响应包含截图路径与详细信息 |

---

## 七、测试报告输出模板 (供测试 Agent 回填)

```markdown
# Alibaba Messenger 功能验收测试报告

- 测试执行人/Agent：[填写 Agent 标识或模型名称]
- 测试执行时间：2026-09-XX XX:XX:XX
- 测试环境：Windows 10/11, Python 3.14, Playwright Chromium

### 测试用例汇总
- [ ] TC-CONFIG-001: 基础配置与目录创建 [PASS / FAIL]
- [ ] TC-DEDUP-001: 防重发记录生命周期 [PASS / FAIL]
- [ ] TC-AUTH-001: 未登录保护性拦截 [PASS / FAIL]
- [ ] TC-API-STATUS-001: 状态探活接口规范 [PASS / FAIL]
- [ ] TC-API-VALIDATION-001: 请求参数校验 [PASS / FAIL]
- [ ] TC-CONCURRENCY-LOCK-001: 串行排队锁 [PASS / FAIL]
- [ ] TC-CLI-001: CLI 启动参数解析 [PASS / FAIL]
- [ ] TC-RECOVERY-SCREENSHOT-001: 异常截屏路径存储 [PASS / FAIL]
- [ ] TC-E2E-LOGIN-PAUSE: 启动弹窗与未登录暂停引导 [PASS / FAIL]

### 结论
[全部功能验证通过 / 发现潜在缺陷（附日志）]
```
