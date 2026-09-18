#!/bin/sh
set -eu
stamp=$(date +%Y%m%d-%H%M%S)
out="backups/$stamp"
mkdir -p "$out"
docker compose exec -T db sh -lc 'mariadb-dump -u root -p"$MARIADB_ROOT_PASSWORD" --single-transaction "$MARIADB_DATABASE"' > "$out/database.sql"
docker run --rm -v fusanhe-crm_espocrm-data:/source:ro -v "$PWD/$out":/backup alpine tar czf /backup/espocrm-data.tgz -C /source .
git rev-parse HEAD > "$out/git-commit.txt"
printf 'Backup created: %s\n' "$out"
