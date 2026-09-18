.PHONY: up down restart logs ps pull config rebuild bootstrap check backup

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

pull:
	docker compose pull

config:
	docker compose config --quiet

rebuild:
	docker compose exec -T espocrm bin/command rebuild

bootstrap:
	set -a; . ./.env; set +a; python3 scripts/bootstrap.py

check:
	docker compose config --quiet
	docker compose exec -T espocrm bin/command app-check
	docker compose exec -T espocrm sh -lc 'find custom -name "*.php" -print0 | xargs -0 -n1 php -l'

backup:
	./scripts/backup.sh
