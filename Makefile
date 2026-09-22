.PHONY: up down restart logs ps pull config rebuild bootstrap check backup spec-check verify-offline

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

spec-check:
	./.specify/scripts/bash/check-prerequisites.sh --json --require-spec --require-tasks --include-tasks
	@test -s .specify/memory/constitution.md
	@test -s specs/001-system-baseline/spec.md
	@test -s specs/001-system-baseline/plan.md
	@test -s specs/001-system-baseline/tasks.md
	@test -s specs/002-non-channel-production-readiness/spec.md
	@test -s specs/002-non-channel-production-readiness/plan.md
	@test -s specs/002-non-channel-production-readiness/tasks.md
	@! rg -n '\[(PROJECT_NAME|PRINCIPLE_[0-9]+_(NAME|DESCRIPTION)|SECTION_[0-9]+_(NAME|CONTENT)|GOVERNANCE_RULES|CONSTITUTION_VERSION|RATIFICATION_DATE|LAST_AMENDED_DATE|FEATURE NAME|DATE)\]' .specify/memory/constitution.md specs/001-system-baseline
	@python3 -c 'import re,pathlib; p=pathlib.Path("specs/001-system-baseline/tasks.md"); lines=[x for x in p.read_text().splitlines() if x.startswith("- [")]; bad=[x for x in lines if not re.match(r"^- \[[ x]\] T\d{3}( \[P\])?( \[US\d+\])? .+`[^`]+`",x)]; raise SystemExit("Invalid task format:\n"+"\n".join(bad) if bad else 0)'
	@python3 -c 'import re,pathlib; p=pathlib.Path("specs/002-non-channel-production-readiness/tasks.md"); lines=[x for x in p.read_text().splitlines() if x.startswith("- [")]; bad=[x for x in lines if not re.match(r"^- \[[ x]\] T\d{3}( \[P\])?( \[US\d+\])? .+`[^`]+`",x)]; raise SystemExit("Invalid task format:\n"+"\n".join(bad) if bad else 0)'

verify-offline:
	docker compose config --quiet
	python3 -m unittest tests.test_contracts tests.test_phase1 tests.test_api_contract tests.test_agent_credentials tests.test_knowledge_scanner_contract tests.test_backup_contract
