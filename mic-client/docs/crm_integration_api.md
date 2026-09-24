# Made-in-China (中国制造网) Gateway - CRM 对接与开放接口文档

本文档面向 CRM 开发人员与系统集成工程师，详细说明中国制造网自动化网关（`mic-gateway`）的 API 规范、认证鉴权、数据模型、业务流程及调用示例，以便顺利对接客户管理系统（CRM）。

---

## 目录
1. [服务架构与工作机制](#1-服务架构与工作机制)
2. [认证鉴权与 API Key 规范](#2-认证鉴权与-api-key-规范)
3. [健康检查与登录态监控](#3-健康检查与登录态监控)
4. [订单接口 (Orders API)](#4-订单接口-orders-api)
5. [询盘会话接口 (Conversations API)](#5-询盘会话接口-conversations-api)
6. [消息历史接口 (Messages API)](#6-消息历史接口-messages-api)
7. [消息发送与出件箱状态机 (Outbox Sending API)](#7-消息发送与出件箱状态机-outbox-sending-api)
8. [商业安全合规策略 (Commercial Policy)](#8-商业安全合规策略-commercial-policy)
9. [CRM 对接最佳实践与代码示例](#9-crm-对接最佳实践与代码示例)
10. [全局错误码规范 (Error Codes)](#10-全局错误码规范-error-codes)

---

## 1. 服务架构与工作机制

网关作为 Made-in-China 供应商后台（Virtual Office & TradeMessenger）与内部业务系统（CRM / AI Agent）之间的安全代理中间件：

```
+-------------+         HTTP / REST API          +-------------------------+
|   内部 CRM   | <=============================> |   Made-in-China Gateway |
|  / AI Agent |     (X-API-Key 鉴权 / JSON)      |      (本地 Windows 运行)   |
+-------------+                                  +-------------------------+
                                                              ||
                                                 Playwright   || 自动同步 &
                                                 自动化实例    || 安全出件箱
                                                              \/
                                                 +-------------------------+
                                                 |   Made-in-China 供应商站  |
                                                 |  (网页后台 / TradeMessenger) |
                                                 +-------------------------+
```

### 核心特性
- **数据解耦**：所有来自平台的订单、询盘和聊天记录都会实时增量同步入网关本地数据库（SQLite WAL 模式），CRM 的高频查询直接走本地数据库，不增加平台风控压力。
- **安全发信（Outbox Pattern）**：CRM / Agent 发信采用异步安全出件箱机制，支持**幂等去重（Idempotency Key）**、**商业敏感信息自动审查拦截**与**浏览器自动化精准派发**。
- **服务地址**：默认监听 `http://127.0.0.1:8787`（或可信内网 IP，由 Windows 防火墙守护）。

---

## 2. 认证鉴权与 API Key 规范

### 2.1 请求头鉴权
网关所有业务接口均强制要求在 HTTP 请求头中携带 `X-API-Key`：
```http
X-API-Key: mic_xxxxxx...
```

### 2.2 角色与最小权限划分
网关支持基于 Argon2 哈希存储的 API Key，按职责划分角色权限：

| 角色代码 | 角色名称 | 权限范围 | 适用客户端 |
| :--- | :--- | :--- | :--- |
| `crm_read` | CRM 只读客户端 | 允许查询订单、询盘、聊天记录、发信任务状态与系统健康度 | 业务 CRM、BI 报表系统 |
| `agent_send` | 自动化发信 Agent | 允许向指定会话提交经过合规审查的非商业消息 | 客服 AI Agent、自动跟进脚本 |
| `admin` | 管理员 | 拥有所有只读和发信权限，并可触发手动全量同步 (`/v1/admin/sync`) | 运维工具、管理控制台 |

### 2.3 生成 API Key 命令
在部署网关的服务器终端执行：
```powershell
# 生成 CRM 只读密钥
.\.venv\Scripts\python.exe -m mic_gateway.cli create-api-key --name crm-prod --role crm_read

# 生成 Agent 发信密钥
.\.venv\Scripts\python.exe -m mic_gateway.cli create-api-key --name agent-prod --role agent_send
```

---

## 3. 健康检查与登录态监控

### 3.1 存活探针 (Liveness)
用于监控网关进程是否在线。

- **请求**：`GET /health/live`
- **认证**：无需认证
- **响应**：`200 OK`
```json
{
  "status": "alive"
}
```

### 3.2 就绪探针 (Readiness)
用于监控网关数据库及中国制造网账号的当前会话是否处于健康登录状态。

- **请求**：`GET /health/ready`
- **认证**：无需认证
- **响应**：
  - 正常可用：`200 OK`
    ```json
    {
      "status": "ready"
    }
    ```
  - 需要登录/异常：`503 Service Unavailable`
    ```json
    {
      "status": "not_ready",
      "code": "authentication_required"
    }
    ```

### 3.3 系统运行状态快照
获取网关当前详细运行指标、数据同步时间点与队列状态。

- **请求**：`GET /v1/status`
- **权限**：`crm_read` 或 `admin`
- **响应**：`200 OK`
```json
{
  "state": "healthy",
  "browser_session": "authenticated",
  "outbox_queue_depth": 0,
  "checkpoints": {
    "conversations": {
      "last_success_at": "2026-09-22T02:00:00Z",
      "failure_count": 0
    },
    "orders": {
      "last_success_at": "2026-09-22T02:00:00Z",
      "failure_count": 0
    }
  }
}
```

---

## 4. 订单接口 (Orders API)

### 4.1 分页获取订单列表
获取从中国制造网同步的订单数据。采用游标分页（Cursor-based Pagination）。

- **请求**：`GET /v1/orders`
- **权限**：`crm_read`
- **Query 参数**：
  - `limit` (int, 可选, 默认 50, 最大 200)：每页记录数。
  - `cursor` (string, 可选)：上一页返回的 `next_cursor`。
  - `updated_after` (ISO 8601 UTC 时间串, 可选)：仅拉取指定时间之后更新的订单（如 `2026-09-20T00:00:00Z`）。
  - `status` (string, 可选)：按订单状态筛选。
  - `buyer` (string, 可选)：按买家参考号筛选。

- **响应**：`200 OK`
```json
{
  "items": [
    {
      "id": "7a35e236-c4d6-4409-a417-83214878a87b",
      "source_id": "ORD100982341",
      "status": "WAIT_BUYER_PAY",
      "buyer_reference": "EEnxEJQbMJmm",
      "currency": "USD",
      "total_amount": "1250.00",
      "source_created_at": "2026-09-21T08:30:00Z",
      "source_updated_at": "2026-09-21T09:15:00Z",
      "synced_at": "2026-09-22T01:00:00Z",
      "lines": [
        {
          "id": "03fa4109-12a1-43ee-8761-92b02871ad54",
          "source_line_id": "LINE-01",
          "sku": "FSH-MTP-400G",
          "name": "Meat Tender Powder 400g*12",
          "quantity": "200",
          "unit_price": "6.25"
        }
      ]
    }
  ],
  "next_cursor": "MjAyNi0wOS0yMVQwOToxNTowMFp8N2EzNWUyMzY..."
}
```

### 4.2 获取单个订单详情
- **请求**：`GET /v1/orders/{order_id}`
- **权限**：`crm_read`
- **路径参数**：`order_id` (UUID，网关订单主键 ID)
- **响应**：`200 OK`（结构同单个 OrderResponse）

---

## 5. 询盘会话接口 (Conversations API)

每个会话代表一个买家对某一产品或商机的沟通主线（对应平台上的 Inquiry / 会话）。

### 5.1 获取会话列表
- **请求**：`GET /v1/conversations`
- **权限**：`crm_read`
- **Query 参数**：
  - `limit` (int, 可选, 默认 50, 最大 200)
  - `cursor` (string, 可选)：游标标记
  - `updated_after` (ISO 8601 UTC, 可选)：增量更新过滤
  - `unread` (bool, 可选)：`true` 仅返回包含未读消息的会话
  - `buyer` (string, 可选)：按买家参考号过滤

- **响应**：`200 OK`
```json
{
  "items": [
    {
      "id": "c10a16ec-e014-4e86-adaf-910c93a1654d",
      "source_id": "rwKpdOGJfYoM",
      "buyer_reference": "EEnxEJQbMJmm",
      "inquiry_subject": "Demander sur Poudre de tendreté de viande raisonnablement formulée 400g*12...",
      "unread": false,
      "last_message_at": "2026-09-22T02:26:47Z",
      "source_updated_at": "2026-09-22T02:26:47Z",
      "synced_at": "2026-09-22T02:27:00Z"
    }
  ],
  "next_cursor": null
}
```

> **注意**：
> - `id` 为网关系统内部生成的唯一 UUID，在 CRM 中关联会话时**以此 ID 为主键**；
> - `source_id` 为中国制造网平台的原生 ID（如 `rwKpdOGJfYoM`）；
> - `buyer_reference` 为买家联系人标识（如 `EEnxEJQbMJmm`）。

---

## 6. 消息历史接口 (Messages API)

获取指定询盘会话下的完整双向沟通记录。

### 6.1 分页获取会话消息历史
- **请求**：`GET /v1/conversations/{conversation_id}/messages`
- **权限**：`crm_read`
- **路径参数**：`conversation_id` (UUID，网关会话 ID)
- **Query 参数**：
  - `limit` (int, 可选, 默认 50, 最大 200)
  - `cursor` (string, 可选)

- **响应**：`200 OK`
```json
{
  "items": [
    {
      "id": "a953e5c7-2009-482d-88cb-854728518cf6",
      "source_id": "rwKpdOGJfYoM:inquiry",
      "conversation_id": "c10a16ec-e014-4e86-adaf-910c93a1654d",
      "direction": "inbound",
      "sender_label": "Mireille Sacrifice",
      "content": "Bonjour, pourriez-vous me donner plus d'informations sur ce produit? Tels que prix, les spécifications, les services après-vente, etc.",
      "attachment_metadata": [],
      "source_created_at": "2026-07-29T11:34:06Z",
      "synced_at": "2026-09-22T01:00:00Z",
      "outbound_job_id": null
    },
    {
      "id": "e8832a67-24ef-4933-91ec-21f42701b7a2",
      "source_id": "6406d74d-f1df-4599-b677-cf1bbd6df125",
      "conversation_id": "c10a16ec-e014-4e86-adaf-910c93a1654d",
      "direction": "outbound",
      "sender_label": "Xiesujun",
      "content": "Bonjour M. Mireille Sacrifice,\n\nNous faisons suite à votre demande concernant notre poudre d'attendrisseur de viande.\n\nAvez-vous des nouvelles ou des besoins particuliers concernant l'avancement de votre projet ? Nous restons à votre entière disposition.\n\nCordialement,\nGuangzhou Fusanhe Food Co., Ltd",
      "attachment_metadata": [],
      "source_created_at": "2026-09-22T02:26:47Z",
      "synced_at": "2026-09-22T02:27:00Z",
      "outbound_job_id": "045d88aa-81d1-49ee-8036-a6c395aca96b"
    }
  ],
  "next_cursor": null
}
```

> **字段说明**：
> - `direction`：
>   - `inbound`：买家发来的询盘或消息。
>   - `outbound`：我方（供应商）发出的回复。
> - `outbound_job_id`：如果是通过网关发信 API 投递的消息，此处会关联其出件箱 Job ID；若在网页上手动发送则为 `null`。

---

## 7. 消息发送与出件箱状态机 (Outbox Sending API)

为了保证发送的高可用与防重复发送，消息提交采用 **安全出件箱机制（Outbox Pattern）**：
1. 客户端提交发信请求，网关完成合规校验后存入 Outbox，立即返回 `202 Accepted` 及任务信息。
2. 后台出件箱工人（Worker）通过真实 Chromium 自动化操作 TradeMessenger 发出消息，并监听 DOM 确保发送成功。
3. 客户端可通过 Job 接口轮询或等待状态更新。

### 7.1 提交发送消息
- **请求**：`POST /v1/conversations/{conversation_id}/messages`
- **权限**：`agent_send` 或 `admin`
- **限流**：每个 API Key 默认 10 次/分钟
- **请求体 (JSON)**：
```json
{
  "idempotency_key": "crm-msg-unique-uuid-001",
  "intent": "non_commercial_followup",
  "content": "Bonjour M. Mireille Sacrifice,\n\nNous faisons suite à votre demande concernant notre poudre d'attendrisseur de viande.\n\nAvez-vous des nouvelles ou des besoins particuliers concernant l'avancement de votre projet ?\n\nCordialement,\nGuangzhou Fusanhe Food Co., Ltd",
  "caller_reference": "CRM-TICKET-8892"
}
```

#### 请求参数约束：
| 字段 | 类型 | 必填 | 约束说明 |
| :--- | :--- | :--- | :--- |
| `idempotency_key` | string | 是 | 客户端生成的幂等键（1~128字符）。相同 key 再次提交时直接返回已有 Job，杜绝重复发信。 |
| `intent` | string | 是 | 意图分类（见下文意图列表）。 |
| `content` | string | 是 | 消息文本（1~4000字符）。必须符合商业合规要求。 |
| `caller_reference` | string | 否 | 业务调用方自定义追踪标（如 CRM 工单编号、客户经理工号等）。 |

#### 允许的意图分类 (`intent`)：
- `greeting`：初次打招呼 / 问候
- `received_acknowledgement`：确认收到买家需求
- `holiday_wishes`：节假日问候 / 祝福
- `non_commercial_followup`：非商业性常规进度跟进

- **响应**：`202 Accepted`
```json
{
  "id": "045d88aa-81d1-49ee-8036-a6c395aca96b",
  "conversation_id": "c10a16ec-e014-4e86-adaf-910c93a1654d",
  "intent": "non_commercial_followup",
  "caller_reference": "CRM-TICKET-8892",
  "request_id": "req-9a12c8b0-51ef",
  "state": "queued",
  "attempt_count": 0,
  "next_attempt_at": null,
  "attempted_at": null,
  "sent_at": null,
  "failure_code": null,
  "safe_result_metadata": {},
  "created_at": "2026-09-22T02:20:00Z",
  "updated_at": "2026-09-22T02:20:00Z"
}
```

### 7.2 查询发信任务状态
- **请求**：`GET /v1/jobs/{job_id}`
- **权限**：`crm_read` 或 `agent_send`
- **路径参数**：`job_id` (UUID，出件箱任务 ID)

- **响应示例 (发送成功)**：`200 OK`
```json
{
  "id": "045d88aa-81d1-49ee-8036-a6c395aca96b",
  "conversation_id": "c10a16ec-e014-4e86-adaf-910c93a1654d",
  "intent": "non_commercial_followup",
  "caller_reference": "CRM-TICKET-8892",
  "request_id": "req-9a12c8b0-51ef",
  "state": "sent",
  "attempt_count": 1,
  "next_attempt_at": null,
  "attempted_at": "2026-09-22T02:26:40Z",
  "sent_at": "2026-09-22T02:26:47Z",
  "failure_code": null,
  "safe_result_metadata": {
    "source_message_id": "6406d74d-f1df-4599-b677-cf1bbd6df125"
  },
  "created_at": "2026-09-22T02:20:00Z",
  "updated_at": "2026-09-22T02:26:47Z"
}
```

### 7.3 出件箱状态流转说明 (`state`)

```
[POST 请求]
    |
    v
+-----------------------+   商业敏感内容 (价格/交期/退款)
| 合规审查 (Policy)     | ----------------------------------> [ requires_human_review ]
+-----------------------+                                         (需人工在后台审核)
    | 审核合规
    v
[ queued ] <----------------------------------------+
    |                                                | (临时网络错误, 自动指数退避重试)
    v                                                |
[ sending ] (Worker 调度浏览器发信)                    |
    |                                                |
    +-----> 发送成功，捕获到平台真实回执 --------------> [ sent ]
    |
    +-----> 永久失败 (会话不存在/买家账号关闭) -----------> [ failed ]
    |
    +-----> 发送已点击但回执超时未确认 (防重复发送) -------> [ uncertain ]
                                                         (自动进入对账恢复机制)
```

---

## 8. 商业安全合规策略 (Commercial Policy)

为防止 AI Agent 或自动化流程未经人工授权误发报价与承诺，网关内置了严格的规则审查拦截机制：

### 8.1 自动拦截规则（触发即降级为 `requires_human_review`）
任何包含以下语义或关键词的消息，**绝对不会自动发送**，将直接保留在任务列表等待人工审批：
1. **价格与货币**：包含数字加货币单位（如 `$5.20`, `USD 6.0`, `100元`, `€`, `GBP`, `FOB`, `CIF`）。
2. **折扣与付款条款**：包含 `discount`, `down payment`, `T/T`, `L/C`, `PayPal`, `Bank transfer`。
3. **承诺交期与库存**：包含 `lead time 7 days`, `in stock`, `ready to ship next week`。
4. **合同、争议与退款**：包含 `contract`, `sign`, `refund`, `dispute`, `compensation`。

### 8.2 允许自动发送的内容
- 询问客户项目进展、规格偏好、联系方式确认。
- 确认已收到客户图纸或需求。
- 元旦、圣诞、开斋节等节假日礼节性问候。

---

## 9. CRM 对接最佳实践与代码示例

### 9.1 Python 对接 SDK 示例

```python
import time
import uuid
import requests

class MICGatewayClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    def check_health(self) -> bool:
        """检查网关与平台登录态"""
        res = requests.get(f"{self.base_url}/health/ready", timeout=5)
        return res.status_code == 200

    def get_unread_conversations(self, limit=50) -> list:
        """拉取有未读消息的会话列表"""
        url = f"{self.base_url}/v1/conversations"
        params = {"unread": "true", "limit": limit}
        res = requests.get(url, headers=self.headers, params=params, timeout=10)
        res.raise_for_status()
        return res.json().get("items", [])

    def get_messages(self, conversation_id: str) -> list:
        """拉取指定会话的历史消息"""
        url = f"{self.base_url}/v1/conversations/{conversation_id}/messages"
        res = requests.get(url, headers=self.headers, timeout=10)
        res.raise_for_status()
        return res.json().get("items", [])

    def send_followup_message(self, conversation_id: str, content: str, ticket_no: str) -> dict:
        """发送跟进消息（支持自动轮询等待结果）"""
        url = f"{self.base_url}/v1/conversations/{conversation_id}/messages"
        payload = {
            "idempotency_key": str(uuid.uuid4()),
            "intent": "non_commercial_followup",
            "content": content,
            "caller_reference": ticket_no
        }
        res = requests.post(url, headers=self.headers, json=payload, timeout=10)
        res.raise_for_status()
        job = res.json()
        job_id = job["id"]

        # 轮询检查发送结果（最多等待 30 秒）
        for _ in range(15):
            time.sleep(2)
            check_res = requests.get(f"{self.base_url}/v1/jobs/{job_id}", headers=self.headers, timeout=5)
            status_data = check_res.json()
            if status_data["state"] in ("sent", "failed", "requires_human_review"):
                return status_data
        return status_data

# 使用示例
if __name__ == "__main__":
    client = MICGatewayClient("http://127.0.0.1:8787", "mic_your_api_key_here")
    
    if client.check_health():
        conversations = client.get_unread_conversations()
        print(f"当前有 {len(conversations)} 个未读询盘")
```

---

### 9.2 Node.js / TypeScript 对接示例

```typescript
import axios from 'axios';
import { randomUUID } from 'crypto';

const gatewayApi = axios.create({
  baseURL: 'http://127.0.0.1:8787/v1',
  headers: {
    'X-API-Key': 'mic_your_api_key_here',
    'Content-Type': 'application/json'
  }
});

// 发送跟进消息示例
async function sendFollowup(conversationId: string, text: string) {
  const response = await gatewayApi.post(`/conversations/${conversationId}/messages`, {
    idempotency_key: randomUUID(),
    intent: 'non_commercial_followup',
    content: text,
    caller_reference: 'CRM-LEAD-1002'
  });

  const job = response.data;
  console.log(`已提交出件箱，Job ID: ${job.id}, 初始状态: ${job.state}`);
  return job;
}
```

---

### 9.3 cURL 命令行调试示例

```bash
# 1. 查询健康与登录就绪状态
curl -i http://127.0.0.1:8787/health/ready

# 2. 查询会话列表
curl -H "X-API-Key: mic_your_crm_key" \
     http://127.0.0.1:8787/v1/conversations?limit=10

# 3. 查询指定会话的聊天历史
curl -H "X-API-Key: mic_your_crm_key" \
     http://127.0.0.1:8787/v1/conversations/c10a16ec-e014-4e86-adaf-910c93a1654d/messages

# 4. 提交发信请求
curl -X POST \
     -H "X-API-Key: mic_your_agent_key" \
     -H "Content-Type: application/json" \
     -d '{
       "idempotency_key": "test-key-001",
       "intent": "greeting",
       "content": "Hello, thank you for your inquiry. We have received your request."
     }' \
     http://127.0.0.1:8787/v1/conversations/c10a16ec-e014-4e86-adaf-910c93a1654d/messages

# 5. 查询发信结果
curl -H "X-API-Key: mic_your_agent_key" \
     http://127.0.0.1:8787/v1/jobs/045d88aa-81d1-49ee-8036-a6c395aca96b
```

---

## 10. 全局错误码规范 (Error Codes)

当 HTTP 状态码非 `2xx` 时，网关返回标准 JSON 错误格式：
```json
{
  "error": {
    "code": "resource_not_found",
    "message": "The requested resource was not found.",
    "request_id": "req-9a12c8b0-51ef"
  }
}
```

| HTTP 状态码 | 错误码 (`code`) | 含义说明 | CRM 处理建议 |
| :--- | :--- | :--- | :--- |
| `401` | `unauthorized` | 缺少 `X-API-Key` 或密钥格式错误 | 检查请求头配置 |
| `403` | `forbidden` | API Key 权限不足（如用 `crm_read` 调用发信接口） | 检查角色授权分配 |
| `404` | `resource_not_found` | 指定的 `order_id`、`conversation_id` 或 `job_id` 不存在 | 核对 ID 是否准确 |
| `409` | `idempotency_conflict` | 相同的 `idempotency_key` 尝试提交了不同的 payload | 换用新的唯一 `idempotency_key` |
| `422` | `validation_error` | 参数字段不符合约束（如时间格式不是 UTC、内容超长等） | 核对字段类型和参数格式 |
| `429` | `rate_limit_exceeded` | 超过了接口频率限制（默认发信 10 次/分钟） | 稍后重试或调整调用节奏 |
| `503` | `shutting_down` | 网关正在维护重启，暂停写入 | 稍后退避重试 |
| `503` | `not_ready` / `authentication_required` | 平台未登录或登录态过期 | 提醒管理员登录后台，恢复后自动工作 |
| `503` | `database_unavailable` | 本地 SQLite 连接失败 | 检查服务器磁盘空间与权限 |
