# Quickstart: 非渠道生产化收敛

```bash
make spec-check
make verify-offline
docker compose config --quiet
docker compose exec -T espocrm sh -lc 'find custom -name "*.php" -print0 | xargs -0 -n1 php -l'
cd android-client && ./gradlew testDebugUnitTest lintDebug assembleDebug
```

运行时权限、Agent 凭证与恢复演练需要隔离环境和测试凭证。全程保持 `FUSANHE_OUTBOUND_PAUSED=true`。
