# Alibaba Messenger API 开发者对接文档 (CRM 集成指南)

本文档专为独立 **CRM 系统、工单系统、营销自动化平台（ERP/OA）** 与 **阿里巴巴国际站自动发信服务 (Alibaba Messenger)** 进行深度对接而编写。

---

## 一、系统架构与运行机制

### 1.1 架构简图
```text
┌─────────────────────────────────────────────────────────────┐
│                    企业 CRM / 业务系统                      │
│   (客户画像 / 营销自动化 / 沉睡商机跟进 / 节日关怀调度)     │
└──────────────┬───────────────────────────────▲──────────────┘
               │ HTTP RESTful API (JSON)       │ 异步回调/轮询
               ▼                               │
┌─────────────────────────────────────────────────────────────┐
│             Alibaba Messenger 服务 (FastAPI)                │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ 串行排队锁 (asyncio.Lock) + 正在排队计数器          │   │
│   └──────────────────────────┬──────────────────────────┘   │
│                              │ 串行调度                     │
│   ┌──────────────────────────▼──────────────────────────┐   │
│   │ Playwright 控制器 (AlibabaMessengerBot)             │   │
│   │ - 指纹伪装与反风控机制 (消除 webdriver 特征)        │   │
│   │ - 拟人化打字模拟 (20ms~80ms 随机按键延时)           │   │
│   │ - 发送后强制拟人化冷却 (3s~6s)                      │   │
│   │ - 双层防重发校验 (本地哈希流水 + 页面气泡比对)       │   │
│   │ - 现场异常智能截屏留痕 (logs/screenshots/)          │   │
│   └──────────────────────────┬──────────────────────────┘   │
│                              │ 持久化 Profile 维持登录态    │
│   ┌──────────────────────────▼──────────────────────────┐   │
│   │ 阿里国际站后台 (message.alibaba.com)                │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心对接原则
1. **浏览器串行性**：底层操作基于真实浏览器会话，同时只能执行一个页面交互任务。FastAPI 服务层内置了严格的 `asyncio.Lock` 排队机制，CRM 并发调用不会导致浏览器崩溃或状态混乱，但耗时会顺序累加。
2. **CRM 异步化集成建议**：强烈建议在 CRM 侧使用**异步任务队列**（如 Celery、Redis Queue、Bull、RabbitMQ 等）来调用发送接口，避免在 Web 前端同步阻塞等待。
3. **长期持久化免登**：服务基于 `alibaba_messenger/profile` 目录持久化存储浏览器 Cookie 和 LocalStorage。首次启动扫码登录后，后续可长期免登；若登录态过期，接口会返回明确的 `401 NEED_LOGIN`。

---

## 二、基础环境与网络配置

* **基础请求地址 (Base URL)**：`http://127.0.0.1:8000`（若部署在局域网服务器，可通过启动参数 `--host 0.0.0.0` 绑定局域网 IP）
* **接口数据格式**：所有请求与响应均采用标准 `UTF-8` 编码，`Content-Type: application/json`
* **交互式在线文档**：
  * **Swagger UI**：`http://127.0.0.1:8000/docs`
  * **ReDoc**：`http://127.0.0.1:8000/redoc`
  * **OpenAPI Schema**：`http://127.0.0.1:8000/openapi.json`

---

## 三、统一响应数据模型

所有接口统一返回如下标准 JSON 结构：

```json
{
  "code": 200,             // 业务 HTTP 状态码 (200, 401, 404, 409, 429, 500)
  "success": true,         // 请求是否完全执行成功 (true / false)
  "status": "SENT",        // 状态字符串标识 (READY, SENT, DUPLICATE_IGNORED 等)
  "message": "执行结果描述",
  "data": { ... }          // 业务数据载荷 (对象或数组，出错时附带现场上下文)
}
```

---

## 四、全量 API 接口详述

### 4.1 服务状态与登录态探测 (`GET /api/status`)
* **请求路径**：`GET /api/status`
* **接口作用**：供 CRM 做健康检查、保活探针或在触发批量推送前检测服务就绪状态。
* **请求参数**：无

#### 响应示例 (HTTP 200 OK)
```json
{
  "code": 200,
  "success": true,
  "status": "READY",
  "message": "服务正常运行",
  "data": {
    "is_logged_in": true,        // 阿里国际站当前是否处于登录状态
    "is_busy": false,           // 机器人当前是否正在操作页面
    "waiting_queue_count": 0    // 当前锁队列中等待排队的请求数量
  }
}
```
* **CRM 应对建议**：若 `is_logged_in: false`，应在 CRM 管理后台展示“国际站登录失效，请联系运维扫码”的醒目标签，暂停自动外发任务。

---

### 4.2 登录状态主动刷新检测 (`POST /api/login/check`)
* **请求路径**：`POST /api/login/check`
* **接口作用**：主动向阿里国际站发起导航与页面检测，核验当前 Cookie 是否仍然有效。
* **请求参数**：无

#### 响应说明
* **已登录 (HTTP 200 OK)**：`{"code": 200, "success": true, "status": "READY", "message": "登录态有效"}`
* **未登录 (HTTP 401 Unauthorized)**：`{"code": 401, "success": false, "status": "NEED_LOGIN", "message": "尚未登录或登录已失效"}`

---

### 4.3 获取最近商机会话列表 (`GET /api/conversations`)
* **请求路径**：`GET /api/conversations`
* **接口作用**：从国际站后台读取商机沟通列表，包含买家姓名、国家国旗、询盘单号、更新时间、未读状态与最新摘要。可用于 CRM 同步最近联系人或未读消息提醒。

#### Query 查询参数
| 参数名 | 类型 | 必填 | 默认值 | 约束 | 描述 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `limit` | integer | 否 | `20` | 1 ~ 100 | 拉取的商机会话条数 |
| `timeout_seconds` | integer | 否 | `30` | ≥ 5 | 获取并发排队锁的最大等待秒数 |

#### 响应示例 (HTTP 200 OK)
```json
{
  "code": 200,
  "success": true,
  "status": "READY",
  "message": "成功获取 10 个商机会话",
  "data": {
    "conversations": [
      {
        "buyer_name": "Kelvin Tay",
        "country": "MY",
        "inquiry_id": "13898396617",
        "last_message": "Hello Kelvin, hope you are having a great week!...",
        "last_time": "16:34",
        "create_time": "2026-08-19",
        "status": "洽谈中",
        "category": "TM 商机",
        "unread_count": 0,
        "has_unread": false
      }
    ],
    "total": 1,
    "elapsed_seconds": 2.15
  }
}
```

---

### 4.4 读取买家/商机完整历史记录 (`GET /api/message/history`)
* **请求路径**：`GET /api/message/history`
* **接口作用**：进入指定商机详情抽屉，**自动向上翻页滚动并点击“查看更多历史消息”**，抓取双方全部往来消息。自动完成阿里翻译水印深度清洗、头像噪点过滤、中英文分离并**严格按时间从旧到新正序排列**。

#### Query 查询参数
| 参数名 | 类型 | 必填 | 默认值 | 约束 | 描述 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `inquiry_id` | string | **二选一** | `null` | - | 阿里询价单号（**强烈推荐，定位唯一且支持跨页检索**） |
| `buyer_name` | string | **二选一** | `null` | - | 买家姓名 / 旺旺名（如无单号时使用） |
| `limit` | integer | 否 | `0` | ≥ 0 | 拉取条数。`0` 表示拉取**全量完整记录**；`N > 0` 表示截取**最新的 N 条** |
| `order` | string | 否 | `"asc"` | `asc` \| `desc` | 排序规则：`asc`（时间正序/从旧到新），`desc`（时间倒序/从新到旧） |
| `timeout_seconds` | integer | 否 | `30` | ≥ 5 | 排队等待超时（秒） |

#### 响应示例 (HTTP 200 OK)
```json
{
  "code": 200,
  "success": true,
  "status": "READY",
  "message": "成功获取买家 [Kelvin Tay] 的完整会话记录 (共 7 条)",
  "data": {
    "buyer_name": "Kelvin Tay",
    "inquiry_id": "13898396617",
    "messages": [
      {
        "sender": "buyer",
        "content": "Mochi Flour 5kg Easy-to-Use Pastry Mix 100% Pure...",
        "translation": "",
        "time": "2026-08-19 05:31",
        "type": "initial_inquiry" // 首条原始询盘单据卡片
      },
      {
        "sender": "seller",
        "content": "Hello! Our mochi powder is soft and stretchy.",
        "translation": "Hello! Our mochi powder is soft and stretchy.",
        "time": "2026-08-19 05:32"
      },
      {
        "sender": "seller",
        "content": "Hello Kelvin, hope you are having a great week!...",
        "translation": "Hello Kelvin, hope you are having a great week!...",
        "time": "2026-09-21 16:34"
      }
    ],
    "total": 3,
    "elapsed_seconds": 3.42
  }
}
```

---

### 4.5 发送实时消息 (`POST /api/message/send`)
* **请求路径**：`POST /api/message/send`
* **接口作用**：向指定客户发送文本消息。
* **执行特性**：
  1. 跨页智能寻路（自动扫描商机沟通多页并翻页）；
  2. 自动唤醒两阶段详情页编辑框（展开 TinyMCE 富文本组件）；
  3. 模拟人类逐字键盘敲击打字，随机输入间隔（20ms ~ 80ms）；
  4. 聚焦真实发送按钮并触发即时发送；
  5. 强制 3 ~ 6 秒安全冷却休眠，避免风控；
  6. 本地与页面双层防重复发送拦截（相同买家在当天内发送完全一致的内容会自动拦截）；
  7. 操作结果截屏存照留痕归档。

#### 请求 Body (JSON)
| 字段名 | 类型 | 必填 | 默认值 | 描述与建议 |
| :--- | :--- | :--- | :--- | :--- |
| `buyer_name` | string | **是** | - | 买家姓名 / 旺旺名（如 `"Kelvin Tay"`） |
| `message` | string | **是** | - | 待发送的消息纯文本内容（最少 10 字符，阿里系统要求） |
| `inquiry_id` | string | 否 | `null` | **强烈建议提供**，如 `"13898396617"`。提供单号可实现跨页精准秒级匹配 |
| `force_send` | boolean | 否 | `false` | 是否强制发送。若设为 `true`，将跳过本地流水与页面气泡查重 |
| `timeout_seconds` | integer | 否 | `30` | 请求在锁队列中等待的最大秒数 |

#### 请求示例
```json
{
  "buyer_name": "Kelvin Tay",
  "inquiry_id": "13898396617",
  "message": "Hello Kelvin, hope you are having a great week! If you still have any demand for the mochi powder or custard powder, please feel free to let us know. We are always ready to support you with our latest catalog and best prices.",
  "force_send": false
}
```

#### 成功响应 (HTTP 200 OK)
```json
{
  "code": 200,
  "success": true,
  "status": "SENT",
  "message": "成功向买家 [Kelvin Tay] 发送消息",
  "data": {
    "buyer_name": "Kelvin Tay",
    "inquiry_id": "13898396617",
    "message": "Hello Kelvin, hope you are having a great week!...",
    "sent_at": "2026-09-21T16:34:25.640472",
    "screenshot": "G:\\FSH\\alibb\\alibaba_messenger\\logs\\screenshots\\sent_13898396617_1789979659.png",
    "elapsed_seconds": 25.18
  }
}
```

---

## 五、状态码与错误处理矩阵 (Error Matrix)

当请求遇到业务异常或校验不通过时，接口会返回对应的 HTTP 状态码，并在 JSON 中返回详细原因：

| HTTP Code | `status` 标识 | 业务含义 | CRM 系统应对与处置策略 |
| :---: | :--- | :--- | :--- |
| **`200`** | `SENT` / `READY` | 执行成功 | 登记 CRM 发送流水，更新客户最后跟进时间。 |
| **`401`** | `NEED_LOGIN` | 阿里登录已失效 | **紧急中断发信队列**，触发通知管理员/运营人员在宿主机完成扫码登录。 |
| **`404`** | `BUYER_NOT_FOUND` | 未检索到目标买家/商机 | 标记该客户“商机单号/姓名不匹配”，转人工跟进核实客户在阿里后台的名称。 |
| **`409`** | `DUPLICATE_IGNORED` | 防重拦截：今日已发过相同内容 | **无需报错**。视为已触达或防打扰成功。如确实需强行补发，可传 `force_send=true`。 |
| **`422`** | `VALIDATION_ERROR` | 请求参数格式错误 | 检查请求 Body，确保 `buyer_name`、`message` 非空，单次内容 ≥ 10 字符。 |
| **`429`** | `QUEUE_TIMEOUT` | 并发请求排队超时 | 浏览器前序任务耗时较长，CRM 可在 **5~10 秒后退避重试**该任务。 |
| **`500`** | `SEND_FAILED` | 自动化执行发生意外 | 查看返回的 `data.screenshot_path` 截屏排查页面异常（如遮罩弹窗等）。 |

---

## 六、CRM 系统生产级接入最佳实践

### 6.1 采用后台异步任务队列 (强烈推荐)
由于一次拟人化发信操作（翻页定位 + 唤醒编辑器 + 逐字键入 + 冷却保护）通常耗时 **15 ~ 30 秒**，**切勿在 CRM 用户的 Web 请求主线程中同步调用**。
- **推荐架构**：CRM 触发发信 -> 写入本地待发信任务表 / Redis 队列 -> 后台 Worker 逐条出队调用 `POST /api/message/send` -> 更新 CRM 发信结果与截屏路径。

### 6.2 频率控制与反风控（每日限量与间隔建议）
1. **单账号建议日发上限**：建议单店铺账号每日自动发送问候/关怀量控制在 **50 ~ 150 封**以内，模拟正常业务员的工作负荷。
2. **批次延时设置**：若 CRM 需批量发送多条商机跟进，每个任务之间建议在 CRM 调度器中增加 **10 ~ 30 秒的随机休眠间隔**。

### 6.3 幂等性设计
* 保持 `force_send: false`（默认值）。
* 即使 CRM 重复调度了同一批名单，Alibaba Messenger 会在 **0 秒内**通过本地哈希索引拦截重复文本，保护海外买家免受骚扰。

---

## 七、多语言对接代码示例

### 7.1 Python 对接示例 (`requests`)
```python
import requests

API_BASE = "http://127.0.0.1:8000"

def send_alibaba_inquiry_greeting(buyer_name: str, inquiry_id: str, content: str):
    payload = {
        "buyer_name": buyer_name,
        "inquiry_id": inquiry_id,
        "message": content,
        "force_send": False,
        "timeout_seconds": 60
    }
    try:
        response = requests.post(f"{API_BASE}/api/message/send", json=payload, timeout=65)
        res_json = response.json()
        
        if response.status_code == 200:
            print(f"✅ 发送成功！存证截屏: {res_json['data']['screenshot']}")
            return True, res_json
        elif response.status_code == 409:
            print(f"⚠️ 今日已发送过该内容，已自动跳过: {res_json['message']}")
            return True, res_json
        elif response.status_code == 401:
            print("🚨 国际站登录态失效，请及时扫码！")
            return False, res_json
        else:
            print(f"❌ 业务失败 [{response.status_code}]: {res_json['message']}")
            return False, res_json
    except requests.exceptions.RequestException as e:
        print(f"网络连接异常: {e}")
        return False, None

# 使用示例
if __name__ == "__main__":
    send_alibaba_inquiry_greeting(
        buyer_name="Kelvin Tay",
        inquiry_id="13898396617",
        content="Hello Kelvin, hope you are having a great week! If you still have any demand for the mochi powder or custard powder, please feel free to let us know."
    )
```

---

### 7.2 Node.js / JavaScript 对接示例 (`axios`)
```javascript
const axios = require('axios');

const client = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 65000,
  headers: { 'Content-Type': 'application/json' }
});

async function sendMessage(buyerName, inquiryId, message) {
  try {
    const res = await client.post('/api/message/send', {
      buyer_name: buyerName,
      inquiry_id: inquiryId,
      message: message,
      force_send: false
    });
    console.log('✅ 发送成功:', res.data);
    return res.data;
  } catch (error) {
    if (error.response) {
      const { status, data } = error.response;
      if (status === 409) {
        console.warn('⚠️ 重复消息已跳过:', data.message);
      } else if (status === 401) {
        console.error('🚨 需要重新扫码登录阿里国际站！');
      } else {
        console.error(`❌ 发送失败 [${status}]:`, data.message);
      }
    } else {
      console.error('网络通信错误:', error.message);
    }
  }
}
```

---

### 7.3 PHP 对接示例 (原生 cURL)
```php
<?php

function sendAlibabaMessage($buyerName, $inquiryId, $message) {
    $url = "http://127.0.0.1:8000/api/message/send";
    $payload = json_encode([
        "buyer_name" => $buyerName,
        "inquiry_id" => $inquiryId,
        "message"    => $message,
        "force_send" => false
    ], JSON_UNESCAPED_UNICODE);

    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
    curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 65);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/json',
        'Content-Length: ' . strlen($payload)
    ]);

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $result = json_decode($response, true);
    if ($httpCode === 200) {
        // 发送成功
        return ["success" => true, "data" => $result];
    } elseif ($httpCode === 409) {
        // 重复跳过
        return ["success" => true, "duplicate" => true, "data" => $result];
    } else {
        // 异常
        return ["success" => false, "code" => $httpCode, "data" => $result];
    }
}
```

---

### 7.4 Java 对接示例 (Spring `RestTemplate`)
```java
import org.springframework.http.*;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;
import java.util.HashMap;
import java.util.Map;

public class AlibabaMessengerService {
    private final RestTemplate restTemplate = new RestTemplate();
    private final String baseUrl = "http://127.0.0.1:8000";

    public boolean sendMessage(String buyerName, String inquiryId, String message) {
        String url = baseUrl + "/api/message/send";
        Map<String, Object> body = new HashMap<>();
        body.put("buyer_name", buyerName);
        body.put("inquiry_id", inquiryId);
        body.put("message", message);
        body.put("force_send", false);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            return response.getStatusCode() == HttpStatus.OK;
        } catch (HttpClientErrorException.Conflict e) {
            System.out.println("防重拦截，今日已发过该文本");
            return true;
        } catch (Exception e) {
            System.err.println("发信接口调用异常: " + e.getMessage());
            return false;
        }
    }
}
```

---

## 八、常见问题与排错手册 (FAQ)

### Q1：启动时报错 `Failed to create a ProcessSingleton for your profile directory`？
* **原因**：本地已有其他 Python 脚本或未关闭的 Playwright Chromium 进程正持有 `alibaba_messenger/profile` 目录的文件排他锁。
* **解决方法**：在终端终止残留的 Playwright 进程：
  ```powershell
  Get-Process -Name chrome | Where-Object { $_.Path -like '*ms-playwright*' } | Stop-Process -Force
  ```

### Q2：为什么发送一条消息需要 20 ~ 30 秒？
* **设计原理**：阿里国际站具备严格的反自动化机器人风控策略。服务内严格执行了：
  1. 跨页检索商机行并点击进入详情页（~3 秒）；
  2. 拟人化字符敲击打字，每个字符随机间隔 20ms~80ms（长文本打字需 3~8 秒）；
  3. 发送完毕后强制执行 3~6 秒冷却等待，保护店铺账号安全。
* **应对策略**：CRM 必须采用异步任务队列解耦，不要在用户界面同步等待。

### Q3：如何将服务部署到服务器并在局域网内给多台电脑的 CRM 使用？
* **启动命令指定主机与端口**：
  ```bash
  python -m alibaba_messenger.run_server --host 0.0.0.0 --port 8000
  ```
* 此时局域网内的 CRM 服务器即可通过 `http://<机器内网IP>:8000` 自由发起对接。
