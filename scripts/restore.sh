#!/bin/sh
set -eu
[ "$#" -eq 1 ] || { echo "Usage: $0 backups/YYYYMMDD-HHMMSS"; exit 2; }
source_dir=$1
[ -f "$source_dir/database.sql" ] && [ -f "$source_dir/espocrm-data.tgz" ] || { echo "Invalid backup directory"; exit 2; }
docker compose stop espocrm daemon websocket
docker compose exec -T db sh -lc 'mariadb -u root -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' < "$source_dir/database.sql"
docker run --rm -v fusanhe-crm_espocrm-data:/target -v "$PWD/$source_dir":/backup:ro alpine sh -c 'rm -rf /target/* && tar xzf /backup/espocrm-data.tgz -C /target'
docker compose up -d
