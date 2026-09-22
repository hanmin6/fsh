# 福三和外贸 CRM 与 AI 回复工作台

基于 EspoCRM 10.0.8 的外贸业务软件，包含两个并列入口：CRM 客户关系与销售推进、AI 客服统一收件与回复协作。系统将外部询盘、客户匹配、知识资料、AI 回复草稿、人工审核、食品外贸业务记录和广州 Windows 平台执行端放在一个可审计的流程里。

当前环境默认禁止自动外发。CRM 已实现受独立 Agent 凭据保护的 Alibaba 入库端点，支持受限批次校验、幂等回放和审计；Alibaba Bridge 的完整回填/增量执行端、真实发送仍未接入，且 PHP/Docker 运行时尚未验证。其他渠道使用占位连接器演示完整闭环。食品外贸模块已完成实体、工作流、接口、布局和测试，默认通过 Feature Flag 隐藏。

## 架构

```mermaid
flowchart LR
  MY[马来西亚独立站] -->|广州主动拉取 / 幂等| CRM[广州 EspoCRM]
  ALI[阿里国际站] -. 官方 API / 执行端 .-> CRM
  MIC[Made-in-China] -. 官方 API / 执行端 .-> CRM
  CRM --> DB[(MariaDB)]
  SHARE[广州共享盘] -->|只读挂载和索引| CRM
  CRM -->|已审核知识 + 会话上下文| AI[第三方 AI API]
  CRM -->|人工批准后的任务| AGENT[4070 Windows 执行端]
  AGENT -->|发送结果 / 风控状态| CRM
```

- CRM 数据库位于本机 Docker volume，不放在 SMB 共享盘。
- `custom/` 和 `client/custom/` 直接从仓库挂载，全部二开可进行 Git 版本管理。
- 共享盘在生产部署时映射到 `KNOWLEDGE_BASE_PATH` 和 `MATERIAL_LIBRARY_PATH`；原始视频不提交给 AI。
- AI API Key、执行端 Token 和数据库密码只保存在被 Git 忽略的 `.env`。

## 已实现

- 8 个 EspoCRM 实体：渠道、会话、消息、AI 草稿、发送任务、知识文档、执行端、审计日志。
- CRM 与 AI 客服双模块入口、共享客户身份、人工身份确认、客服转销售、人工接管和双向跳转；会话状态、销售阶段、发送任务状态分别维护。
- 统一询盘列表的渠道、负责人、状态、国家和未读字段，以及按最后消息时间排序的数据基础。
- 会话详情工作台：客户资料、消息时间线、AI 草稿编辑和人工批准区。
- 客户匹配顺序：平台用户 ID、邮箱、手机号、公司加国家、姓名加公司；无法可靠匹配时保留待确认身份，必须由人工显式关联或建档。
- 消息、会话和发送任务的数据库唯一约束。
- OpenAI Compatible Provider；未配置 Key 时使用确定性的 Mock AI。
- PDF、DOCX、XLSX、TXT、Markdown 扫描和校验值更新。PDF 文本提取在容器存在 `pdftotext` 时启用。
- Alibaba、MadeInChina、Website、Email 的连接器骨架及可演示的 MockConnector。
- 执行端注册、心跳、任务领取、发送中、成功/失败回写、三次重试、领取超时、审计和每 Agent 独立凭据轮换。
- `POST /Fusanhe/alibaba/sync`：受 Agent capability 约束的 Alibaba 入库、回放冲突保护、身份/Lead 关联和消息去重；这不是完整的平台抓取执行端。
- 全局停发开关，默认 `true`。
- “外贸运营概览”Dashlet，展示询盘、待回复、待审核、超时、负责人、响应时间、AI 修改率和发送结果。
- 老板、业务主管、业务员和平台执行端的权限基线；管理员使用 EspoCRM 内置管理员权限。
- 食品外贸业务模块：产品与规格版本、证书与检测报告、样品、询价、报价/PI、轻量销售订单和分批交付；每个模块有服务端状态机、权限保护、幂等或冻结规则及 Feature Flag。
- Android `1.0.0` UI 演示版：客户新增、客户历史、询盘会话、翻译和 AI 回复建议，当前使用本地 Mock Repository。

## 目录

```text
custom/Espo/Custom/                 PHP、metadata、布局、API 路由
client/custom/src/                  EspoCRM 客户端工作台与 Dashlet
knowledge/demo/                     可提交的演示知识资料
materials/                          本地素材挂载点，不提交内容
scripts/bootstrap.py                幂等安装导航和角色
scripts/mock-agent.py               一次性模拟 Windows 执行端
scripts/backup.sh                   数据库和运行数据备份
scripts/restore.sh                  备份恢复（需明确传入备份目录）
docs/permissions.md                 角色权限说明
docs/API_AGENT_HANDOFF.md           接口开发交接与技术债
docs/PROJECT_STATUS.md              项目完成度与版本基线
docs/RELEASE_HANDOFF_2026-09-21.md  本次整合发布、验证、回退和分支说明
android-client/                     Android 1.0.0 UI 演示版
```

## 启动和安装

```bash
cp .env.example .env
# 修改所有 change-me 值，并为 FUSANHE_AUTOMATION_TOKEN 生成长随机值
docker compose up -d
docker compose exec espocrm bin/command rebuild
set -a; source .env; set +a
python3 scripts/bootstrap.py
```

打开 <http://localhost:8080>。左侧导航包含 CRM、AI 客服、统一询盘、知识文档和发送任务；食品外贸实体是否显示由 `.env` 中的 Feature Flag 决定。老板看板可在首页添加 Dashlet“外贸运营概览”。

升级自定义代码后执行：

```bash
docker compose exec espocrm bin/command rebuild
```

## 环境变量

| 变量 | 用途 |
|---|---|
| `AI_API_BASE_URL` | OpenAI Compatible `/v1` 根地址 |
| `AI_API_KEY` | 留空时使用 Mock AI |
| `AI_MODEL` | 模型名 |
| `AI_TIMEOUT` / `AI_MAX_RETRIES` | 超时秒数和重试次数 |
| `KNOWLEDGE_BASE_PATH` | 容器内知识库目录 |
| `MATERIAL_LIBRARY_PATH` | 容器内素材目录 |
| `FUSANHE_AUTOMATION_TOKEN` | Agent 注册/轮换使用的 bootstrap Token；同步与任务接口使用每 Agent 凭据 |
| `FUSANHE_OUTBOUND_PAUSED` | 全局停发开关，生产初始化为 `true` |
| `ALIBABA_BRIDGE_URL` | Alibaba Bridge 地址 |
| `ALIBABA_BRIDGE_TOKEN` | Alibaba Bridge Token，不得提交到 Git |
| `FUSANHE_FEATURE_PRODUCTS` | 产品与规格模块开关，默认关闭 |
| `FUSANHE_FEATURE_CERTIFICATES` | 证书与检测报告模块开关，默认关闭 |
| `FUSANHE_FEATURE_SAMPLES` | 样品模块开关，默认关闭 |
| `FUSANHE_FEATURE_QUOTES` | 询价、报价和 PI 模块开关，默认关闭 |
| `FUSANHE_FEATURE_ORDERS` | 销售订单和分批交付模块开关，默认关闭 |

修改环境变量后使用 `docker compose up -d --force-recreate espocrm` 使 Apache 进程读取新值。

## Mock 演示

1. 管理员调用 `POST /api/v1/Fusanhe/mock/intake` 导入演示询盘。
2. 在“统一询盘”打开会话，点击“生成 AI 草稿”。
3. 修改草稿并点击“批准并创建发送任务”。
4. 保持 `FUSANHE_OUTBOUND_PAUSED=true` 时，执行端无法领取任务。
5. 仅在演示环境把开关改为 `false`，重建 CRM 容器后运行：

```bash
set -a; source .env; set +a
python3 scripts/mock-agent.py
```

6. 演示后立即恢复 `FUSANHE_OUTBOUND_PAUSED=true` 并重建 CRM 容器。

真实连接器不得直接复用网页选择器写进 CRM。接入优先级为官方 API、邮件或接口组合、浏览器自动化、Windows UI 自动化。

## Android 客户端

Android 项目位于 `android-client/`。当前版本为 `1.0.0` UI 演示版，使用 Kotlin、Jetpack Compose、Material 3、Hilt、StateFlow、Room 占位和 Retrofit 占位。

```bash
cd android-client
./gradlew testDebugUnitTest assembleDebug
```

当前 Android 客户端没有连接真实 CRM。详细功能、Mock 数据和接入方式见 `android-client/README.md` 与 `android-client/docs/BACKEND_API_MAPPING.md`。

## 备份与恢复

```bash
make backup
# 恢复会覆盖当前数据库，必须明确指定目录
./scripts/restore.sh backups/20260918-120000
```

备份包含 MariaDB dump、EspoCRM `data` volume 和当前 Git 提交信息。共享盘原始素材应使用广州文件服务器自己的快照与异地备份。

## 故障处理

```bash
docker compose ps
docker compose logs --tail=200 espocrm daemon websocket db
docker compose exec espocrm bin/command app-check
docker compose exec espocrm bin/command rebuild
```

- 页面没有新模块：运行 rebuild，强制刷新浏览器，再运行 `scripts/bootstrap.py`。
- AI 失败：检查 API 地址、Key、模型名、超时以及容器出网。
- 执行端领不到任务：检查全局停发开关、Token、任务是否已批准以及是否存在同会话活跃任务。
- 登录失效、验证码、页面变化或风控：执行端通过心跳上报，人工处理后再恢复发送。

## 已知限制

- Alibaba CRM 入库端点与每 Agent 凭据已实现，但 Alibaba 全量/增量抓取执行端、Bridge 实际接通和真实平台发送均未完成；当前 PHP/Docker 运行时也未验证。Made-in-China、独立站和邮件仍是接口骨架。
- 浏览器或 Windows UI 自动化执行程序尚未实现。
- 食品外贸模块目前是 CRM 内的结构化业务记录与工作流，尚未连接 ERP、工厂排产、物流承运商或真实收付款系统；Feature Flag 只控制可见性，不替代权限。
- Android 1.0.0 使用本地 Mock 数据，真实认证、数据库、WebSocket、离线同步和消息发送尚未接入。
- DOCX/XLSX 使用轻量文本提取；复杂表格和扫描 PDF 后续应接专业解析/OCR 服务。
- 当前共享目录为本地演示挂载，部署到广州 Windows 时需替换为实际共享盘路径并配置只读权限。
