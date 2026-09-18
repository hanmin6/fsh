.PHONY: up down restart logs ps pull config

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
