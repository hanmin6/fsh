# 福三和外贸 CRM · Android 客户端（UI 演示版）

版本：`1.0.0`（`versionCode 1`）

面向外贸业务员的移动端工作台：新增客户、查看客户历史、实时翻译与 AI 回复建议。
**当前阶段为纯 UI 演示**：全部数据来自本地 Mock Repository，不连接真实数据库，不发送任何真实消息。

## 环境要求

| 组件 | 版本要求 |
| --- | --- |
| Android Studio | Ladybug（2024.2）或更新 |
| JDK | 17+（Android Studio 自带 JBR 即可） |
| Android SDK | Compile SDK 35，Build Tools 35.0.0 |
| Gradle | 8.10.2（项目已含 Wrapper，无需手动安装） |
| Kotlin | 2.0.21（版本目录统一管理） |
| 模拟器/真机 | Android 8.0（API 26）及以上 |

## 启动方式

1. 用 Android Studio 打开 `android-client/` 目录；
2. 等待 Gradle Sync 完成；
3. 选择模拟器或真机，点击 Run ▶ 即可。
4. 命令行方式：`./gradlew :app:assembleDebug`，产物位于 `app/build/outputs/apk/debug/`。

首次进入 App 流程：启动页 → 登录页（任意合法邮箱 + 非空密码，或点「跳过登录（演示模式）」）→ 工作台。

## 技术栈

- Kotlin + Jetpack Compose + Material 3（森林绿品牌浅色主题，深色主题结构已预留）
- Navigation Compose（底部四 Tab：工作台 / 客户 / 询盘 / 我的）
- ViewModel + Kotlin Coroutines + StateFlow
- Repository 分层：`domain/repository` 接口 + `data/repository` 实现（当前全部为 Mock 实现）
- Hilt 依赖注入（`di/DataModule` 中一处绑定即可切换真实实现）
- Retrofit + OkHttp 接口占位（`data/remote`，当前未被调用）
- Room 本地缓存占位（`data/local`，当前未被仓库使用）

## 项目结构

```
android-client/app/src/main/java/com/fusanhe/crm/
├── FusanheApplication.kt / MainActivity.kt
├── di/                      # Hilt：ApplicationScope、DataModule(仓库绑定)、NetworkModule(Retrofit占位)、数据库
├── domain/
│   ├── model/               # Customer / Conversation / Message / AIReplySuggestion / CustomerHistoryItem ...
│   ├── repository/          # CustomerRepository / ConversationRepository / AIReplyRepository / TranslationRepository / SettingsRepository / SessionRepository / NotificationRepository
│   └── usecase/             # ValidateNewCustomerUseCase / DetectDuplicateCustomerUseCase
├── data/
│   ├── model/               # （预留）网络 DTO 与领域模型映射
│   ├── mock/                # MockData 数据源 + MockModeController(演示失败/离线开关)
│   ├── remote/              # Retrofit CrmApiService 占位 + EspoCRM 风格 DTO
│   ├── local/               # Room 占位：Entities / DAOs / CrmDatabase
│   └── repository/          # MockXxxRepository 全部实现
├── ui/
│   ├── FusanheApp.kt        # 导航壳 + 底部导航
│   ├── MainViewModel.kt     # 登录态 / 询盘未读徽标
│   ├── navigation/Routes.kt
│   ├── theme/               # 品牌色 / 字体 / 圆角 / 主题
│   ├── components/          # 通用组件：状态徽章、空态、错误态、骨架屏、排序筛选条等
│   ├── common/UiState.kt    # Loading / Content / Empty / Error
│   └── screens/             # 各页面（每页独立 ViewModel 与 UiState）
│       ├── splash/  login/  dashboard/
│       ├── customers/  addcustomer/  customerdetail/  customersearch/
│       ├── conversations/  chat/（含 AI 建议弹层、翻译编辑弹层、常用语弹层）
│       └── notifications/  profile/  settings/
└── util/TimeFormat.kt
```

## 页面列表

| # | 页面 | 路由 | 说明 |
| --- | --- | --- | --- |
| 1 | 启动页 | `splash` | 品牌展示，1.2s 后按登录态跳转 |
| 2 | 登录页 | `login` | 演示校验，不请求真实后端 |
| 3 | 工作台 | `dashboard` | 今日新增询盘 / 待回复 / 待审核 / 超时 / 发送异常 / 最近客户与询盘 / 快速新增客户 |
| 4 | 客户列表 | `customers` | 搜索、筛选入口、排序、下拉刷新、骨架屏、分页加载、空态、新增 FAB |
| 5 | 新增客户 | `add_customer` | 四步表单（基本信息/联系方式/商务信息/确认摘要），必填与格式校验、疑似重复提示、防重复提交 |
| 6 | 客户详情 | `customer/{customerId}` | 客户概要 + 跟进概览 + 历史时间线（询盘记录可跳转会话） |
| 7 | 搜索和筛选页 | `customer_search` | 国家/来源/负责人/等级多选筛选 + 实时结果 |
| 8 | 询盘列表 | `conversations` | 状态筛选、超时标记、未读徽标、下拉刷新 |
| 9 | 会话详情 | `chat/{conversationId}` | 客户信息、原文/译文切换、发送状态、附件占位、AI/翻译/常用语/附件操作、输入草稿保留 |
| 10 | AI 回复建议弹层 | 会话内 | 建议/译文/意图/摘要/风险/置信度/缺失信息/引用知识，采用·编辑后采用·重新生成·复制·关闭 |
| 11 | 翻译编辑弹层 | 会话内 | 草稿 ↔ 客户语言互译、交换展示、机器翻译提示、失败重试、采用填入 |
| 12 | 通知与异常 | `notifications` | 发送异常 / 超时 / 审核提醒 / 系统公告，全部已读 |
| 13 | 我的 | `profile` | 个人资料、统计、入口列表、退出登录 |
| 14 | 设置 | `settings` | 主题模式、演示开关（网络/翻译/发送/保存失败、离线）、API 信息 |

## Mock 数据说明

- 数据源在 `data/mock/`：12 个客户、15 个询盘会话、50+ 条双语消息（英/西/日/法 + 中文翻译）、24 条客户历史、5 条预置 AI 建议、常用语、知识资料、通知。
- 时间戳相对当前时间生成，演示数据始终"新鲜"。
- 每 75 秒自动模拟一条客户新消息；可在会话右上角菜单「模拟客户消息」手动触发。
- 新增客户保存在内存 `MockCustomerRepository`，进程存活期间不丢失（旋转屏幕、切换页面安全）。
- **演示开关**（设置页）：模拟网络失败 / 翻译失败 / 发送失败 / 保存失败 / 离线，用于演示各类异常状态。
- 发送消息仅更新本地状态并提示「演示模式：消息不会发送到真实平台」。

### 演示场景索引

- 英文客户询问产品规格：`conv01`（IQF 蓝莓）、`conv06`（冻干草莓，消息缺少完整规格）
- 西班牙语客户询问价格与 MOQ：`conv02`（催折扣 + HALAL 证书，SLA 已超时）
- 客户催交期：`conv03`（苹果脆片，超时）
- 客户询问食品认证：`conv04`（HALAL / ISO22000）
- 客户要求折扣：`conv05`（AI 草稿含折扣承诺 → 高风险需人工确认）
- 高风险回复需人工确认：`conv01`（价格+付款）、`conv05`（折扣）
- 60 天账期请求：`conv09`（含一条发送失败消息）

## 如何切换成真实 Repository

UI 与 ViewModel 只依赖 `domain/repository` 接口，切换无需改动界面：

1. 在 `data/remote/` 下实现 `RemoteCustomerRepository` 等真实实现（复用已定义的 `CrmApiService` 与 DTO，补充 DTO ↔ 领域模型 Mapper）；
2. 在 `di/DataModule.kt` 中把 `@Binds` 的目标从 `MockXxxRepository` 换成 `RemoteXxxRepository`；
3. 需要鉴权时在 `NetworkModule` 的 OkHttpClient 上添加拦截器（EspoCRM 通常为 `X-Espo-Authorization` Basic 认证），API 地址可从 `BuildConfig` 注入；
4. Room 缓存层（`data/local`）可在真实实现中接入做离线缓存。

当前 `NetworkModule` 已提供 Retrofit/OkHttp/`CrmApiService`，但没有任何仓库引用它们。

## 后续需要对接的 CRM API

后端为 EspoCRM 10.0.8（`http://localhost:8080/api/v1`），涉及实体：Account / Contact / Lead / ExternalConversation / ExternalMessage / AIReplyDraft / KnowledgeDocument / OutboundTask。

每个页面所需接口、字段与实时更新方式的完整对照见 **[docs/BACKEND_API_MAPPING.md](docs/BACKEND_API_MAPPING.md)**。

主要接口概览：

| 模块 | 接口（Espo 风格） |
| --- | --- |
| 客户 | `GET /Account`（列表+筛选+分页）、`GET /Account/{id}`、`POST /Account`、`PUT /Account/{id}`、`GET /Account/{id}/externalConversations` |
| 会话 | `GET /ExternalConversation`、`GET /ExternalConversation/{id}` |
| 消息 | `GET /ExternalConversation/{id}/externalMessages`、`POST /ExternalMessage` |
| AI 草稿 | `POST /AIReplyDraft/action/generateReply`、`POST /AIReplyDraft/{id}`（采纳） |
| 知识库 | `GET /KnowledgeDocument` |
| 翻译 | 由 AI 服务代理（建议沿用 AIReplyDraft action 扩展 `translate`） |
| 实时更新 | WebSocket / 轮询 `GET /ExternalConversation` 的 `unreadCount` 与新消息 |

## 已知边界（当前阶段）

- 不连接真实数据库 / 后端 / IM 平台，全部为本地演示；
- 深色主题结构已预留但未做逐页视觉校对；
- 通知、历史等数据在 Mock 中为静态集合，新增客户的历史记录会动态追加；
- 不包含单元测试与 CI（下一阶段接入）。

## 版本验证

`1.0.0` 已执行：

```bash
./gradlew testDebugUnitTest assembleDebug
```

构建成功。当前 `testDebugUnitTest` 为 `NO-SOURCE`，说明尚未建立 Android 单元测试；APK 属于 Debug 构建，不作为正式签名发布包。
