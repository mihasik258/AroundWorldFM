COMPOSE ?= docker compose
PROD = docker compose -f docker-compose.prod.yml

.PHONY: env up down logs ps test test-backend test-bot test-frontend lint import-stations prod-up prod-bot prod-admin prod-import prod-logs prod-backup

env:
	@test -f .env || { cp .env.example .env; \
		sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$$(openssl rand -hex 32)/; \
		s/^SECRET_PEPPER=.*/SECRET_PEPPER=$$(openssl rand -hex 32)/; \
		s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$$(openssl rand -hex 24)/; \
		s/^BOT_API_SECRET=.*/BOT_API_SECRET=$$(openssl rand -hex 32)/" .env; \
		echo ".env created"; }

up: env
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

test: test-backend test-bot test-frontend

test-backend:
	$(COMPOSE) exec -T db psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='aroundfm_test'" | grep -q 1 || \
		$(COMPOSE) exec -T db psql -U postgres -c "CREATE DATABASE aroundfm_test"
	docker build -q --target dev -t aroundfm-backend:dev backend
	docker run --rm --network $$(basename $$PWD | tr 'A-Z' 'a-z')_default -v $$PWD/backend:/app -w /app \
		-e TEST_DATABASE_URL=postgresql+asyncpg://postgres:$${POSTGRES_PASSWORD:-postgrespassword}@db:5432/aroundfm_test \
		aroundfm-backend:dev sh -c "ruff check . && ruff format --check . && mypy && pytest --cov"

test-bot:
	docker build -q --target dev -t aroundfm-bot:dev bot
	docker run --rm -v $$PWD/bot:/app -w /app aroundfm-bot:dev sh -c "ruff check . && ruff format --check . && mypy && pytest --cov"

test-frontend:
	cd frontend && npm ci --no-audit --no-fund && npm run lint && npm run typecheck && npm run test:coverage && npm run build

import-stations:
	$(COMPOSE) exec backend python -m app.cli import-stations --verify $(ARGS)

prod-up:
	$(PROD) up -d --build

prod-bot:
	$(PROD) --profile bot up -d --build

prod-admin:
	$(PROD) run --rm backend python -m app.cli create-admin --username $(USERNAME) --email $(EMAIL)

prod-import:
	$(PROD) exec backend python -m app.cli import-stations --verify $(ARGS)

prod-logs:
	$(PROD) logs -f --tail=200

prod-backup:
	$(PROD) exec backup sh -c 'pg_dump --format=custom --no-owner --file=/backups/manual-$$(date -u +%Y%m%dT%H%M%SZ).dump'
