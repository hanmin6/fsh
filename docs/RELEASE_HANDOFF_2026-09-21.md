# 福三和 CRM 发布交接

发布日期：2026-09-21  
发布分支：`codex/release-crm-food-20260921`  
目标主分支：`main`  
远端：`https://github.com/hanmin6/fsh.git`

## 本次发布范围

本次发布把 CRM + AI 客服第一阶段协作骨架与食品外贸业务骨架整合到同一套 EspoCRM 扩展中。产品上仍是两个并列模块；技术上继续使用同一应用、数据库和权限体系，没有预先拆成微服务。

已纳入：

- CRM/AI 客服双入口、共享客户身份、人工身份确认、客服转销售、客户与会话双向跳转。
- 人工接管、人工草稿、回复快照、Mock/真实执行隔离、停发一致性和状态机保护。
- 产品与规格版本、证书与检测报告、样品、询价、报价/PI、轻量销售订单和分批交付。
- 这些食品模块的实体、布局、语言包、服务、接口、ACL、状态机 Hook、Feature Flag 和测试。

真实渠道同步、自动外发、Android 真实接口、ERP/工厂/物流连接仍不在本次发布范围内。

## 关键提交

发布分支从 ZCode 第一阶段基线继续集成，当前主要提交为：

| 提交 | 内容 |
| --- | --- |
| `f5938d9`–`5af8fb0` | CRM/AI 客服第一阶段协作、权限、状态机和运行时验收 |
| `05ed22b` | 产品与规格版本 |
| `96d1861` | 证书与检测报告 |
| `775703c` | 样品管理 |
| `68c6a16` | 询价、报价与 PI |
| `dca5438` | 订单与分批交付 |
| `f333be3` | 安全加固与 Hook 兼容 |

完成收尾后，最终提交会包含本文件、README、CHANGELOG 和项目状态更新。

## Feature Flag

食品模块默认关闭。需要在 `.env` 中按需设置为 `1` 后重建 CRM 容器：

```dotenv
FUSANHE_FEATURE_PRODUCTS=1
FUSANHE_FEATURE_CERTIFICATES=1
FUSANHE_FEATURE_SAMPLES=1
FUSANHE_FEATURE_QUOTES=1
FUSANHE_FEATURE_ORDERS=1
```

Feature Flag 只负责隐藏导航和接口入口，不是权限机制；服务端 ACL 和工作流保护仍然生效。生产环境继续保持：

```dotenv
FUSANHE_OUTBOUND_PAUSED=true
```

## 验证证据

- JSON metadata、Python 编译和 Shell 语法检查通过。
- 前端 Node 测试 12 项通过。
- 全量 PHP 语法检查和 EspoCRM `app-check` 通过。
- 停发开启回归 74 项通过；隔离环境人工/Mock 发送闭环通过。
- Docker 独立测试栈运行正常，验证端口为 `18090/18091`；不连接真实渠道、不发送真实消息。

详细场景和接口说明见 `docs/PHASE1_ZCODE_HANDOFF.md`、`docs/API_AGENT_HANDOFF.md` 及各 `tests/test_wp*.py`。

## 分支和版本策略

- `main`：已验证的集成基线，只接收经过发布验证的提交。
- `codex/release-crm-food-20260921`：本次发布分支，发布后保留用于追溯。
- `codex/crm-ai-phase1-zcode`：第一阶段 CRM/AI 客服来源分支。
- `codex/android-client-ui`：Android 1.0.0 UI/Mock 基线。
- 发布标签：`fusanhe-v0.5.0`、`crm-api-v0.5.0`、`crm-web-v0.4.0`；Android 继续使用 `android-v1.0.0`。

## 回退办法

1. 代码层：将 `main` 回退到发布前提交，执行 `bin/command rebuild`；新增字段和表残留不会影响旧代码读取。
2. 功能层：将食品模块 Feature Flag 设为空并重建容器，导航和入口恢复隐藏状态。
3. 外发层：保持 `FUSANHE_OUTBOUND_PAUSED=true`；不要通过回退代码绕过停发保护。
4. 测试环境：仅清理由本次创建的独立 Compose 项目，不触碰默认 `fusanhe-crm` 数据卷；如确认不再需要，可执行对应测试栈的 `docker compose ... down -v`。

## 明确未完成

- Alibaba、Made-in-China、独立站、邮件的真实消息同步与发送。
- 自动回复策略、低风险自动发送和真实渠道风控执行端。
- Android 认证、真实 CRM API、翻译服务、WebSocket、离线同步和正式签名包。
- 食品模块与 ERP、工厂排产、仓储、物流、付款/财务系统的连接。
- CI、监控、密钥轮换、正式生产部署和浏览器端到端自动化。
