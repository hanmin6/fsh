# 福三和 CRM 运维手册（非渠道部分）

## 安全基线

- 生产与演练环境保持 `FUSANHE_OUTBOUND_PAUSED=true`，只有渠道正式验收窗口才允许单独解除。
- `.env`、Agent 明文凭证、客户导出和备份不得提交 Git 或粘贴到工单。
- 日志只记录 `X-Request-Id`、稳定错误码和对象 ID，不记录 Token、密码、消息全文或绝对文件路径。
- 知识库只扫描 `KNOWLEDGE_BASE_PATH` 的真实子路径；符号链接、非白名单类型及超过 `FUSANHE_KNOWLEDGE_MAX_BYTES` 的文件会被跳过或隔离报错。

## 健康检查

```bash
docker compose ps
docker compose config --quiet
curl -fsS http://localhost:8080/api/v1/Fusanhe/status
make verify-offline
```

检查 EspoCRM、数据库、daemon、websocket 都处于 healthy/running；`status` 中 `outboundPaused` 应为 `true`。任何异常先记录请求 ID，再查容器日志，禁止直接在生产库试写。

## Agent 凭证签发、轮换与撤销

1. `FUSANHE_AUTOMATION_TOKEN` 只用于 `/Fusanhe/agent/register` 的引导注册，使用长随机值并限制接触人。
2. 注册响应中的 `credential` 只出现一次，立即写入执行端系统密钥库；数据库仅保存 `password_hash`。
3. 心跳、领取、sending、result 请求使用该独立凭证，并且请求体 `agentKey` 必须与凭证绑定。
4. 再次注册同一 `agentKey` 会轮换凭证并增加版本，旧凭证立即失效。紧急撤销时设置该 Agent 的 `credentialRevokedAt`，并把状态改为 offline。
5. `FUSANHE_AUTOMATION_LEGACY_UNTIL` 为空即禁用旧共享口令回退；最迟在 **2026-10-31** 前完成迁移并保持为空。

## 备份与恢复演练

创建备份：

```bash
./scripts/backup.sh
```

目录必须包含 `database.sql`、`espocrm-data.tgz`、`git-commit.txt` 和 `SHA256SUMS`。复制到异地加密存储后抽查：

```bash
cd backups/YYYYMMDD-HHMMSS
shasum -a 256 -c SHA256SUMS
```

恢复只能在隔离环境先演练：

```bash
./scripts/restore.sh backups/YYYYMMDD-HHMMSS
```

脚本会在停服务和覆盖卷之前强制校验清单。恢复后执行 `docker compose ps`、`make check`、登录只读抽查客户/会话/草稿数量，并确认停发开关仍为 true。

## 发布与回退

发布前必须通过 CI 的 Spec、Python、PHP 和 Android 四类门禁，并先创建完整备份。数据库元数据变更使用 EspoCRM rebuild，不手工改 vendor/core。

若发布失败：立即保持停发，停止新版本服务，恢复上一个 Git 版本；涉及数据库或持久卷变化时使用发布前备份恢复。完成健康检查后再开放内部用户，渠道开关仍不得随应用回退自动开启。

## 敏感信息事件

若 Token、备份或客户信息疑似泄漏：先保持停发并撤销相关 Agent 凭证，轮换引导 Token和所有受影响账户；保留请求 ID、时间、Agent key 和操作类型作为审计证据，但不得在事件记录中复制泄漏内容。
