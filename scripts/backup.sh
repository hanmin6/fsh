#!/bin/sh
set -eu
stamp=$(date +%Y%m%d-%H%M%S)
out="backups/$stamp"
mkdir -p "$out"
docker compose exec -T db sh -lc 'mariadb-dump -u root -p"$MARIADB_ROOT_PASSWORD" --single-transaction "$MARIADB_DATABASE"' > "$out/database.sql"
docker run --rm -v fusanhe-crm_espocrm-data:/source:ro -v "$PWD/$out":/backup alpine tar czf /backup/espocrm-data.tgz -C /source .
git rev-parse HEAD > "$out/git-commit.txt"
(
  cd "$out"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum database.sql espocrm-data.tgz git-commit.txt > SHA256SUMS
  else
    shasum -a 256 database.sql espocrm-data.tgz git-commit.txt > SHA256SUMS
  fi
)
printf 'Backup created: %s\n' "$out"
