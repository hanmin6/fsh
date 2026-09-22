# Implementation Plan: 非渠道生产化收敛

**Branch**: `main` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

## Summary

在不接入真实渠道的前提下，完成 CRM API 安全契约、Agent 凭证、知识隔离、Android 真实数据基础、
CI 与可恢复运维。保留现有 EspoCRM/Compose 架构和 Mock 演示。

## Technical Context

**Languages**: PHP 8.x、Python 3.9+、Kotlin/JVM 17、YAML/Shell
**Dependencies**: EspoCRM 10.0.8、MariaDB 11.4、Docker Compose、Retrofit/OkHttp、Room、Hilt、AndroidX Security Crypto
**Testing**: Python unittest、PHP lint、Gradle unit/lint/assemble
**Constraints**: 停发默认开启；不修改 core/vendor；不存明文凭证；不执行真实渠道发送。

## Constitution Check

- Specification Before Change: PASS
- Human-Controlled and Secure by Default: PASS
- Contract and State Integrity: PASS
- Evidence Before Completion: PASS
- Auditable, Reversible Operations: PASS

## Project Structure

```text
custom/Espo/Custom/Tools/Fusanhe/        # API, auth, workflow, knowledge
custom/Espo/Custom/Resources/metadata/   # credential/data schema
android-client/app/src/                  # session, mapper, repositories, tests
tests/                                   # offline/runtime/security regression
.github/workflows/                       # CI
scripts/                                 # backup/restore
docs/                                    # operations/release guidance
```

## Migration Strategy

1. 先增加 Agent 凭证字段与签发流程。
2. 共享 Token 仅用于兼容注册，默认截止日期为 2026-10-31，可通过环境变量提前关闭。
3. Android 默认仍为 Mock，只在显式配置真实模式时启用 Remote Repository。
4. 备份 manifest 是向后兼容增强；无 manifest 的旧备份需显式使用 legacy 选项，默认拒绝。
