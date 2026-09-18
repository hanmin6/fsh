# 福三和 CRM 项目状态

更新时间：2026-09-19

## 当前版本基线

| 组件 | 版本 | 当前状态 |
| --- | --- | --- |
| Docker 基础环境 | CRM MVP 0.1.0 | 本地可运行 |
| Web 工作台 | CRM Web 0.2.0 | MVP 页面完成 |
| CRM 自定义 API | CRM API 0.3.0 | Mock 闭环完成，生产接入未完成 |
| Android 客户端 | Android 1.0.0 | UI 与 Mock 交互完成，真实接口未接入 |

## 已完成资产

- 4 个健康运行的 Docker 服务：MariaDB、EspoCRM、daemon、websocket。
- 8 个 CRM 业务实体和 11 个自定义业务接口。
- Web 登录、导航、首页、询盘、会话、客户、草稿、知识库、发送任务和执行端视图。
- AI 草稿、人工批准、幂等任务、Agent 领取、失败重试和发送结果回写 Mock 闭环。
- Android 97 个可跟踪项目文件，其中 76 个 Kotlin 文件、14 个主要页面和完整 Mock Repository。
- Android 客户新增、历史时间线、会话、翻译、AI 建议和异常状态演示。
- 接口交接、权限、Android 后端映射、备份恢复和版本记录文档。

## 完成度判断

以下比例用于规划，不是验收承诺：

| 范围 | 估算完成度 | 说明 |
| --- | ---: | --- |
| 本地演示 MVP | 85% | Web、后端 Mock 闭环和 Android UI 均可演示 |
| Web 工作台 MVP | 90% | 核心页面完成，仍需大数据量和多角色验收 |
| CRM 接口层 | 70% | 核心流程可用，ACL、Schema、单 Agent 凭证仍缺失 |
| Android 1.0 UI 范围 | 100% | 约定的 UI 和 Mock 功能已完成并成功构建 |
| Android 生产接入 | 10% | Retrofit/Room 只有结构，真实认证、同步和 WebSocket 未实现 |
| 真实渠道接入 | 20% | Alibaba 只有 Bridge 健康检查，消息同步和发送未实现 |
| 生产部署准备 | 40% | 有备份与安全默认值，缺 CI、监控、密钥轮换和正式发布流程 |

## 当前验证证据

- `docker compose config --quiet` 通过。
- EspoCRM `rebuild` 与 `app-check` 通过。
- 29 个自定义 PHP 文件语法检查通过。
- 8 项接口测试通过 7 项，远程 Alibaba 集成测试默认跳过 1 项。
- 2 项运行时闭环测试通过。
- Android `testDebugUnitTest assembleDebug` 构建成功；单元测试当前为 `NO-SOURCE`。
- Android `lintDebug` 通过，报告包含 47 个 Warning、0 个 Error；主要为依赖版本、Compose 参数和本地化提示。
- Android Debug APK 版本：`1.0.0`，最低 Android API 26。

## 下一阶段优先级

### P0：接口安全与契约

1. 为 intake、生成草稿、知识扫描和状态聚合增加细粒度 ACL。
2. 把共享执行端 Token 改成单 Agent 凭证，支持哈希存储、轮换和撤销。
3. 定义统一请求 Schema、错误体、请求 ID 和接口版本。
4. 轮换曾出现在本地未提交文件中的 Bridge、管理员和自动化凭证。

### P1：Android 接入

1. 设计移动端认证与安全存储，避免直接保存管理员密码。
2. 实现 DTO Mapper 和 Remote Repository。
3. 接入客户新增、客户详情、客户历史、询盘与消息读取。
4. 增加翻译接口和 AI 草稿接口映射。
5. 接入 Room 离线缓存、分页、WebSocket 和断线恢复。
6. 建立 Android 单元测试、UI 测试和 CI。

### P1：真实渠道

1. 实现 Alibaba 消息增量同步、Webhook 签名验证和真实发送。
2. 实现独立站、邮件和 Made-in-China 连接器。
3. 建立死信、重试、游标、限流、监控和补偿任务。

## 分支职责

| 分支 | 职责 |
| --- | --- |
| `main` | 已验证的本地集成基线 |
| `codex/fusanhe-crm-frontend` | Web 与 CRM API 基线 |
| `codex/backend-api-v1` | CRM API 0.3.0 里程碑 |
| `codex/android-client-ui` | Android 1.0.0 开发与发布基线 |
| `codex/unified-inbox-mvp` | 历史 MVP 里程碑，只保留追溯 |

当前仓库没有配置 Git remote，因此版本和标签只保存在本机；接入 GitHub 或其他远端后需要推送 `main`、活动分支和标签。
