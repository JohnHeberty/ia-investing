.PHONY: lint typecheck test test-integration test-all build docker-up docker-down docker-test format check

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy src

test:
	pytest tests/unit/ -q --tb=short

test-integration:
	pytest tests/integration/ -q --tb=short -m integration

test-all:
	pytest tests/ -q --tb=short

test-cov:
	pytest tests/ --cov=src --cov-report=term-missing --cov-report=html -q --tb=short

build:
	uv sync --all-extras
	cd web && npm ci && npm run build

docker-up:
	docker compose --profile dev up -d

docker-down:
	docker compose --profile dev down -v --remove-orphans

docker-test:
	docker compose -f docker/compose.yml -f docker/compose.test.yml --profile test up --build --abort-on-container-exit

check: lint typecheck test
