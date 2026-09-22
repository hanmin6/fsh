# Quickstart Validation: 福三和 CRM 全系统基线

## Preconditions

- 只用演示数据和测试凭证。
- `.env` 的 `change-me` 值已替换，且 `FUSANHE_OUTBOUND_PAUSED=true`。
- 本验证不开启真实对外发送。

## Static and Offline Gates

```bash
docker compose config --quiet
python3 -m unittest tests.test_contracts tests.test_phase1
```

Expected: Compose、metadata JSON、路由、唯一索引、安全默认、状态机和食品外贸契约通过；
需真实远端的检查明确跳过而不伪报成功。

## CRM Runtime Gates

```bash
docker compose up -d
docker compose ps
docker compose exec -T espocrm bin/command rebuild
docker compose exec -T espocrm bin/command app-check
docker compose exec -T espocrm sh -lc 'find custom -name "*.php" -print0 | xargs -0 -n1 php -l'
set -a; source .env; set +a
python3 -m unittest tests.test_p0_fixes
python3 tests/test_phase1_runtime.py
python3 tests/verify_runtime.py
python3 -m unittest tests.test_security_regression
python3 -m unittest tests.test_wp1_products tests.test_wp2_certificates \
  tests.test_wp3_samples tests.test_wp4_quotes tests.test_wp7_orders
```

Expected: 四个服务健康；rebuild/app-check/PHP lint 通过；询盘、身份、草稿、批准、任务、重试和审计闭环通过；
伪造状态、越权访问和未知渠道被拒绝；停发开启时 Agent 不能领取或发送。

## Android Gates

```bash
cd android-client
./gradlew testDebugUnitTest lintDebug assembleDebug
```

Expected: 测试、lint 和 Debug APK 构建通过。`NO-SOURCE` 不代表生产接入测试完成；认证、Remote Repository、
Room 同步和断线恢复在 `tasks.md` 中保持未完成。

## Manual P1 Journey

1. 用 `POST /api/v1/Fusanhe/mock/intake` 导入演示询盘。
2. 确认客户身份，或确认它保持待人工匹配。
3. 生成、修改并明确批准 AI 草稿。
4. 确认仅有一个幂等 `OutboundTask`。
5. 保持停发，运行 `python3 scripts/mock-agent.py`，确认无任务被领取。
6. 确认审计包含身份、草稿、批准和停发拒绝证据，不含凭证或完整私密载荷。

## Backup and Restore Drill

```bash
make backup
# 仅在隔离环境对明确备份目录执行
./scripts/restore.sh backups/YYYYMMDD-HHMMSS
```

Expected: 备份含数据库 dump、EspoCRM data volume 和 Git 版本；恢复后核对关键实体数量、状态和审计关联。
恢复会覆盖目标数据，不在未隔离生产环境试运行。

## Evidence Record

每次实施/发布记录日期、Git 提交、环境、通过/失败/跳过数、跳过原因、外部依赖、剩余风险和回退方法。
证据不得含 `.env`、Token、Cookie、客户原文或未脱敏截图。
