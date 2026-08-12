.PHONY: lint typecheck test test-integration test-performance test-all build docker-up docker-down docker-test format check init

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy src

test:
	uv run pytest tests/unit/ -q --tb=short

test-integration:
	uv run pytest tests/integration/ -q --tb=short -m integration

test-performance:
	uv run pytest tests/performance/ -v --tb=short

test-all:
	uv run pytest tests/ -q --tb=short

test-cov:
	uv run pytest tests/ --cov=src --cov-report=term-missing --cov-report=html -q --tb=short

build:
	uv sync --all-extras
	cd web && npm ci && npm run build

init:
	alembic upgrade head
	uv run python scripts/seed_initial_data.py

docker-up:
	docker compose --profile dev up -d

docker-down:
	docker compose --profile dev down -v --remove-orphans

docker-test:
	docker compose -f docker/compose.yml -f docker/compose.test.yml --profile test up --build --abort-on-container-exit

check: lint typecheck test
