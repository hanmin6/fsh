# 阿里巴巴国际站 Playwright 自动发消息服务系统设计规范 (Spec)

- **创建日期**：2026-09-19
- **状态**：已定稿 (Ready for Review)
- **目标组件**：`alibaba_messenger/`

---

## 1. 背景与目标 (Context & Goals)

### 1.1 业务背景
广州福三和食品有限公司需要对阿里巴巴国际站（Alibaba.com）买家客户进行日常问候与节假日关怀跟进。国际站官方开放平台（OpenAPI）未提供完全开放、自由度高的即时消息发送接口，因此需要通过自动化浏览器（Playwright）模拟人工操作完成会话检索与消息投递。

### 1.2 核心目标
1. **浏览器自动化**：基于 Playwright 构建常驻且持久化登录态的国际站消息中心（TradeManager Web）控制器，支持通过买家姓名/公司名定位会话并模拟人工发送纯文本。
2. **CRM 解耦接口**：构建轻量级 FastAPI RESTful 服务，暴露同步发送接口及状态查询接口，供外部 CRM 灵活调用。
3. **安全与防封**：实现去自动化特征、拟人化随机按键延时、发信冷却节流阀、双重防重复校验，保障账号与发送安全。

### 1.3 非目标 (Non-Goals)
- 本模块不负责 CRM 本身的数据流、节假日判断与客户名单筛选（由调用方 CRM 负责）。
- 本模块暂不处理图文附件、卡片及音视频发送（当前版本限定为纯文本消息）。

---

## 2. 总体架构与工程组织 (Architecture)

### 2.1 系统架构
系统由三层构成：
1. **API 网关与调度层 (`server.py`)**：接收 CRM 的 HTTP JSON 请求，利用 `asyncio.Lock` 保证单浏览器上下文串行排队操作，管理接口超时与异常格式化。
2. **自动化核心控制器 (`alibaba_bot.py`)**：封装 Playwright Chromium 实例，常驻持久化用户目录（User Data Dir），执行页面导航、搜索定位、防重判断、按键输入与发送校验。
3. **状态与存储层**：包含浏览器持久化 Session 存储（`profile/`）、发信防重流水记录（`logs/sent_records.json`）、失败诊断截屏（`logs/screenshots/`）。

### 2.2 目录结构
```text
g:\FSH\alibb/
├── alibaba_crm_client.py                 # 原有数据对接客户端（保持独立）
└── alibaba_messenger/                    # [新增自动化发信子系统]
    ├── config.py                         # 配置参数：端口、延时、超时、路径配置
    ├── alibaba_bot.py                    # Playwright 控制器封装
    ├── server.py                         # FastAPI 路由与排队调度
    ├── run_server.py                     # 服务启动入口（支持登录引导与服务拉起）
    ├── requirements.txt                  # 依赖库清单
    ├── profile/                          # [自动生成] 浏览器持久化目录
    └── logs/                             # [自动生成] 运行日志与截屏
        ├── screenshots/                  # 失败时现场截图留痕
        └── sent_records.json             # 防重发流水记录
```

---

## 3. 详细交互流程 (Detailed Flow)

### 3.1 登录与会话初始化流程
1. `run_server.py` 启动时，调用 `AlibabaMessengerBot.start()`。
2. 使用 `playwright.chromium.launch_persistent_context(user_data_dir=PROFILE_DIR, headless=False, ...)` 启动，应用去除 `navigator.webdriver` 特征与真实 User-Agent。
3. 自动导航至阿里国际站消息中心：`https://message.alibaba.com/message/default.htm`。
4. **检测登录状态**：
   - 若 URL 重定向到 `passport.alibaba.com` 或页面出现登录框：终端输出醒目提示并等待人工在弹出的浏览器中完成扫码/密码登录；
   - 登录成功并进入消息中心主页面后，控制器标记 `is_logged_in = True`，`status = "READY"`，FastAPI 正常提供发信服务。

### 3.2 单条消息发送步骤 (`POST /api/message/send`)
1. **排队锁获取**：FastAPI 接收请求后尝试获取 `asyncio.Lock`。若等待时长超过 `timeout_seconds`（默认 30s），立即返回 `QUEUE_TIMEOUT`。
2. **第一层防重校验**：检索本地 `logs/sent_records.json`。若该买家今天已收到完全一致的文本内容，且 `force_send == False`，直接返回 `DUPLICATE_IGNORED`。
3. **搜索定位买家**：
   - 聚焦消息列表顶部的搜索输入框，清空原有内容；
   - 键入 `buyer_name` 并按下 `Enter`（或点击搜索图标）；
   - 等待搜索结果列表加载（超时 5 秒）；
   - 若搜索结果为空或提示“无匹配联系人”，清空搜索框并返回 `BUYER_NOT_FOUND`。
4. **进入对话**：
   - 点击匹配结果第一项，右侧展开对应聊天窗口；
   - 等待消息输入区域变为可交互状态（`contenteditable="true"` 或 `textarea`）。
5. **第二层页面防重校验**：
   - 抓取右侧聊天记录中我方发出的最后一条气泡文本；
   - 若内容完全一致且气泡时间显示为今日，且 `force_send == False`，放弃输入，清空搜索并返回 `DUPLICATE_IGNORED`。
6. **模拟输入与发送**：
   - 鼠标点击输入框获取焦点；
   - 模拟逐字键入（按键间隔随机 20ms ~ 80ms）；
   - 停顿 500ms 后模拟点击“发送”按钮或按下快捷键（`Enter` / `Ctrl+Enter`）；
   - 校验输入框已被清空，并确认发出气泡已出现在屏幕；
7. **记录与收尾**：
   - 写入 `logs/sent_records.json` 登记防重记录；
   - 点击搜索框旁的清除按钮（“X”），恢复列表原始会话状态；
   - 强制休眠 3 ~ 6 秒（模拟人类操作间隔，防风控）；
   - 释放 `asyncio.Lock` 并向 CRM 返回成功响应。
8. **异常自愈**：
   - 若过程中发生任何未预期异常（元素超时、遮罩阻挡等），立即截取当前屏幕保存至 `logs/screenshots/{timestamp}_{buyer_name}.png`；
   - 刷新消息中心页面恢复初始状态，并在返回的 JSON 异常信息中带上截图相对路径。

---

## 4. HTTP API 接口规范 (API Specification)

### 4.1 发送消息接口
- **URL**: `POST /api/message/send`
- **请求体 (JSON)**:
```json
{
  "buyer_name": "string (必填，买家姓名/公司名)",
  "message": "string (必填，发送内容)",
  "force_send": "boolean (可选，默认 false，true 表示忽略防重强制发送)",
  "timeout_seconds": "integer (可选，默认 30，排队及执行总超时秒数)"
}
```
- **成功响应 (200 OK)**:
```json
{
  "code": 200,
  "success": true,
  "status": "SENT",
  "message": "消息发送成功",
  "data": {
    "buyer_name": "ABC Trading Co.",
    "sent_at": "2026-09-19T14:40:00+08:00",
    "elapsed_seconds": 5.2
  }
}
```
- **业务状态码一览**:
  - `code: 200, status: "SENT"`：成功送达
  - `code: 404, status: "BUYER_NOT_FOUND"`：未搜索到指定买家
  - `code: 409, status: "DUPLICATE_IGNORED"`：今日已发送过相同内容，被策略拦截
  - `code: 401, status: "SESSION_EXPIRED"`：国际站登录已失效，需重新扫码
  - `code: 429, status: "QUEUE_TIMEOUT"`：队列繁忙超时
  - `code: 500, status: "SEND_FAILED"`：执行失败（附带 `screenshot_path`）

### 4.2 状态探活接口
- **URL**: `GET /api/status`
- **响应体**:
```json
{
  "code": 200,
  "status": "READY",           // READY | BUSY | NEED_LOGIN | ERROR
  "is_logged_in": true,
  "active_queue_count": 0,
  "uptime_seconds": 3600
}
```

---

## 5. 风控与拟人化参数 (Safety Settings)

| 参数项 | 默认配置 | 说明 |
| :--- | :--- | :--- |
| `TYPING_DELAY_MIN_MS` | `20` | 单字符打字最小随机间隔 (毫秒) |
| `TYPING_DELAY_MAX_MS` | `80` | 单字符打字最大随机间隔 (毫秒) |
| `POST_SEND_COOLDOWN_SEC` | `3.0 ~ 6.0` | 单条消息发送后的强制冷却休眠 (秒) |
| `SEARCH_WAIT_TIMEOUT_MS` | `5000` | 搜索结果渲染最长等待时间 |
| `PAGE_ACTION_TIMEOUT_MS` | `10000` | 页面元素定位与动作超时时间 |

---

## 6. 测试与验证策略 (Verification Plan)
1. **单元/基础测试**：
   - 验证配置类与防重文件读写机制；
   - 验证 FastAPI 接口契约校验（Pydantic 异常捕获）。
2. **模拟页面端到端测试 (Mock/Stub E2E)**：
   - 构建本地简单 HTML 仿真页面模拟阿里消息中心的搜索框、列表项、输入框与发送气泡，验证自动化核心在无真人账号时的行为正确性与超时处理。
3. **真实环境集成验收**：
   - 启动服务并在真实阿里国际站前台打开消息中心，执行一次指定联系人真实发信，确认 CRM 收到 `200 SENT` 响应。
