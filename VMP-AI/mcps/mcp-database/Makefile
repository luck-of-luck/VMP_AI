.PHONY: install lint fmt test test-unit test-integration test-cluster up down mongo-rs seed atlas-local atlas-seed evals eval-postgres eval-mysql eval-mariadb eval-sqlite eval-mongodb eval-redis eval-atlas run bin help

UV ?= uv
EVAL_MODEL ?= sonnet
EVAL_RUN = EVAL_MODEL=$(EVAL_MODEL) $(UV) run python scripts/run_evals.py

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (including dev)
	$(UV) sync

lint: ## Run ruff checks and formatting verification
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests

fmt: ## Auto-fix lint issues and reformat
	$(UV) run ruff check src tests --fix
	$(UV) run ruff format src tests

test-unit: ## Fast tests only (no Docker required)
	$(UV) run pytest tests/unit tests/e2e -v

test-integration: ## Integration tests against real databases (requires Docker)
	$(UV) run pytest tests/integration -v -m "not cluster"

test-cluster: ## Multi-node topology tests: replication, promote, step_down (requires Docker)
	$(UV) run pytest tests/integration -v -m cluster --no-cov

test: ## Full suite with the 95% coverage gate + HTML report in temp/reports/coverage (requires Docker)
	$(UV) run pytest -v -m "not cluster" --cov=mcp_database --cov-report=term-missing --cov-report=html --cov-fail-under=95
	@echo "coverage html: temp/reports/coverage/index.html"

up: ## Start the local playground databases (PostgreSQL, MySQL, MongoDB)
	docker compose up -d

mongo-rs: ## Initialize the MongoDB replica set (run once after 'make up')
	docker compose exec mongodb mongosh --quiet --eval 'try { rs.status() } catch (e) { rs.initiate({_id: "rs0", members: [{_id: 0, host: "localhost:27017"}]}) }'

seed: ## Load deterministic sample data into the playground (required by docs/evals)
	docker compose exec -T postgres psql -q -U dev -d app < scripts/seed/postgres.sql
	docker compose exec -T mysql mysql -uroot -pdev < scripts/seed/mysql.sql
	docker compose exec -T mariadb mariadb -uroot -pdev < scripts/seed/mariadb.sql
	docker compose exec -T mongodb mongosh --quiet < scripts/seed/mongodb.js
	docker compose exec -T redis redis-cli --pipe < scripts/seed/redis.txt
	rm -f temp/playground.db && mkdir -p temp && $(UV) run python scripts/seed/sqlite.py temp/playground.db

atlas-local: ## Start the local Atlas playground (mongod+mongot for $search/$vectorSearch, port 27018)
	docker compose --profile atlas up -d atlas

atlas-seed: ## Seed the Atlas playground with vector demo data (run after 'make atlas-local' is healthy)
	docker compose exec -T atlas mongosh --quiet < scripts/seed/atlas.js

evals: up atlas-local ## One-shot agent evals: playground up + seeded, then all engines via the claude CLI (reports in temp/reports/)
	@echo "waiting for playground databases..."
	@until docker compose exec -T postgres pg_isready -q -U dev -d app 2>/dev/null; do sleep 1; done
	@until docker compose exec -T mysql mysqladmin ping -uroot -pdev --silent >/dev/null 2>&1; do sleep 1; done
	@until docker compose exec -T mariadb mariadb-admin ping -uroot -pdev --silent >/dev/null 2>&1; do sleep 1; done
	@until docker compose exec -T redis redis-cli ping >/dev/null 2>&1; do sleep 1; done
	@until docker compose exec -T mongodb mongosh --quiet --eval 'db.runCommand({ping: 1}).ok' >/dev/null 2>&1; do sleep 1; done
	@until docker compose exec -T atlas mongosh --quiet --eval 'db.runCommand({ping: 1}).ok' >/dev/null 2>&1; do sleep 1; done
	$(MAKE) mongo-rs seed atlas-seed
	@echo "waiting for atlas search indexes..."
	@until docker compose exec -T atlas mongosh --quiet app --eval 'quit(db.articles.aggregate([{$$listSearchIndexes: {}}]).toArray().filter(i => i.queryable).length === 2 ? 0 : 1)' >/dev/null 2>&1; do sleep 2; done
	$(MAKE) eval-postgres eval-mysql eval-mariadb eval-sqlite eval-mongodb eval-redis eval-atlas

eval-postgres: ## Agent evals against playground PostgreSQL (requires 'make up' + 'make seed')
	@mkdir -p temp/reports
	NAME=pg_app URI='postgresql://dev:dev@localhost:5432/app' MODE=read_write \
		$(EVAL_RUN) docs/evals/evaluation-postgres.json temp/reports/evals-postgres.md

eval-mysql: ## Agent evals against playground MySQL (requires 'make up' + 'make seed')
	@mkdir -p temp/reports
	NAME=mysql_app URI='mysql://root:dev@localhost:3306' MODE=read_write \
		$(EVAL_RUN) docs/evals/evaluation-mysql.json temp/reports/evals-mysql.md

eval-mariadb: ## Agent evals against playground MariaDB (requires 'make up' + 'make seed')
	@mkdir -p temp/reports
	NAME=mariadb_app URI='mariadb://root:dev@localhost:3307' MODE=read_write \
		$(EVAL_RUN) docs/evals/evaluation-mariadb.json temp/reports/evals-mariadb.md

eval-sqlite: ## Agent evals against the seeded SQLite playground file (requires 'make seed')
	@mkdir -p temp/reports
	NAME=sqlite_app URI='sqlite:///temp/playground.db' MODE=read_write \
		$(EVAL_RUN) docs/evals/evaluation-sqlite.json temp/reports/evals-sqlite.md

eval-redis: ## Agent evals against playground Redis (requires 'make up' + 'make seed')
	@mkdir -p temp/reports
	NAME=redis_app URI='redis://localhost:6380/0' MODE=read_write \
		$(EVAL_RUN) docs/evals/evaluation-redis.json temp/reports/evals-redis.md

eval-mongodb: ## Agent evals against playground MongoDB (requires 'make up' + 'make mongo-rs' + 'make seed')
	@mkdir -p temp/reports
	NAME=mongo_app URI='mongodb://localhost:27019/app?directConnection=true' MODE=read_write \
		$(EVAL_RUN) docs/evals/evaluation-mongodb.json temp/reports/evals-mongodb.md

eval-atlas: ## Agent evals against the local Atlas playground (requires 'make atlas-local' + 'make atlas-seed')
	@mkdir -p temp/reports
	NAME=atlas_app URI='mongodb://localhost:27018/app?directConnection=true' MODE=read_write \
		$(EVAL_RUN) docs/evals/evaluation-atlas.json temp/reports/evals-atlas.md

down: ## Stop and remove the playground databases
	docker compose --profile atlas down -v

run: ## Run the server against the playground PostgreSQL (one connection per instance)
	NAME=pg_app URI='postgresql://dev:dev@localhost:5432/app' MODE=read_write $(UV) run mcp-database

bin: ## Build a standalone binary at dist/mcp-database (PyInstaller; per-OS/arch)
	$(UV) run --with pyinstaller python scripts/build_binary.py
