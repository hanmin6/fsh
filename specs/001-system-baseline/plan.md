# Implementation Plan: 福三和 CRM 全系统基线

**Branch**: `main` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-system-baseline/spec.md`

## Summary

将现有 Web CRM、AI 客服、食品外贸、渠道执行、Android 和运维资产纳入一个根级 Spec Kit
项目。不重写已有代码；建立业务基线、契约、数据模型、验证入口和可执行缺口清单。后续每个行为变更
使用独立特性目录，保留现有架构与兼容性。

## Technical Context

**Language/Version**: PHP 8.x（EspoCRM 镜像内）、JavaScript（EspoCRM AMD 客户端）、Python 3.9+、Kotlin/JVM 17

**Primary Dependencies**: EspoCRM 10.0.8 Apache、MariaDB 11.4、Docker Compose、Jetpack Compose/Material 3、
Hilt、Retrofit/OkHttp、Room、Kotlin Serialization

**Storage**: MariaDB 是 CRM 与审计系统记录；EspoCRM data volume 存储运行数据；知识/素材挂载只读；
Android Room 是待完成的可重建离线投影。

**Testing**: Python `unittest`契约/安全/运行时测试；PHP `php -l`；EspoCRM `rebuild` / `app-check`；
Docker Compose 健康检查；Gradle `testDebugUnitTest` / `lintDebug` / `assembleDebug`

**Target Platform**: Linux Docker 主机 + Windows 4070 执行端 + Android API 26+

**Project Type**: 单仓库多客户端 Web CRM 与移动应用，共享一个服务端系统记录

**Performance Goals**: 主要列表/详情在正常办公网络下 2 秒内可用；询盘 60 秒内进入收件箱；
任务领取与冲突在 5 秒内返回明确结果。

**Constraints**: 对外发送默认停止；人工批准必经；不修改 EspoCRM core/vendor；密钥和客户私密数据不入 Git；
共享盘只读；Feature Flag 不替代权限；真实渠道需外部凭证与官方契约。

**Scale/Scope**: 单组织；20+ 自定义业务接口；20+ 自定义记录类型；14 个 Android 主要页面；4 类渠道骨架。

## Constitution Check

*GATE: PASS before research and PASS after design.*

- **Specification Before Change**: PASS. 基线含规格、计划、研究、数据模型、契约、验证与任务。
- **Human-Controlled and Secure by Default**: PASS with tracked remediation. 默认停发和人工批准已保留；
  共享 Agent Token 与粗粒度 ACL 是 P0 任务，解决前不得宣称生产就绪。
- **Contract and State Integrity**: PASS with tracked remediation. 已有状态机与唯一索引保留；
  统一请求/错误契约、移动 DTO 和真实渠道契约保持未完成。
- **Evidence Before Completion**: PASS. 已实现与待完成项分开标记，验证命令在 `quickstart.md`。
- **Auditable, Reversible Operations**: PASS with tracked remediation. 已有审计和备份基线；
  恢复演练、凭证生命周期和生产观测是待完成任务。

## Project Structure

### Documentation (this feature)

```text
specs/001-system-baseline/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
├── contracts/system-contracts.md
└── tasks.md
```

### Source Code (repository root)

```text
custom/Espo/Custom/
├── Controllers/                     # entity controllers
├── Hooks/                           # server-side state/write guards
├── Resources/metadata/              # entity, scope, client definitions
├── Resources/routes.json            # custom API routes
└── Tools/Fusanhe/
    ├── Api/                          # API actions
    ├── Connector/                    # channel contracts/adapters
    ├── WorkflowService.php           # inquiry/draft/task workflow
    └── *Service.php                  # identity, food-trade, handoff

client/custom/src/                  # Web workbench and dashboards
android-client/app/src/main/java/com/fusanhe/crm/
├── data/                             # local, remote, mock, repositories
├── domain/                           # models, interfaces, use cases
└── ui/                               # Compose screens/view models
scripts/                            # bootstrap, mock agent, backup, restore, seeds
tests/                              # contract, runtime, workflow, security tests
docs/                               # handoff and status
compose.yaml                        # runtime topology
```

**Structure Decision**: 保留根级单一 Spec Kit 项目。Web、API、Android 共享身份、状态机和契约；
拆分多个 `.specify/` 会使契约所有权模糊。

## Delivery Slices

1. **P0 安全与契约**: 细粒度 ACL、单 Agent 凭证、统一 Schema/错误/请求 ID、密钥轮换。
2. **P1 Android 生产接入**: 移动认证、DTO/Mapper、Remote Repository、Room、分页、WebSocket、测试与 CI。
3. **P1 真实渠道**: Alibaba 同步/签名/发送，再分别接入独立站、邮件和 Made-in-China，增加限流、死信与对账。
4. **P2 生产运维**: CI、监控、备份恢复演练、发布与回退证据。

## Complexity Tracking

无新的宪章违例。已知棕地缺口已转为任务，不构成生产豁免。
