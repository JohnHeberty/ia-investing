#!/usr/bin/env bash
# scripts/test-infra.sh
# Brings up test infrastructure, runs all tests, tears down.
#
# Usage:
#   bash scripts/test-infra.sh              # run all tests
#   bash scripts/test-infra.sh unit         # run only unit tests (no infra needed)
#   bash scripts/test-infra.sh integration  # run only integration tests
#   bash scripts/test-infra.sh down         # tear down infra

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$PROJECT_ROOT/docker"

cd "$PROJECT_ROOT"

ACTION="${1:-all}"

teardown() {
    echo "--- Tearing down test infrastructure ---"
    cd "$COMPOSE_DIR"
    docker compose -f compose.yml -f compose.test.yml --profile test down -v --remove-orphans 2>/dev/null || true
    cd "$PROJECT_ROOT"
}

if [ "$ACTION" = "down" ]; then
    teardown
    exit 0
fi

cleanup_done=false
cleanup() {
    if [ "$cleanup_done" = false ]; then
        teardown
        cleanup_done=true
    fi
}
trap cleanup EXIT

if [ "$ACTION" != "unit" ]; then
    echo "=== Starting test infrastructure (postgres + minio) ==="
    cd "$COMPOSE_DIR"
    docker compose -f compose.yml -f compose.test.yml --profile test up -d --wait
    cd "$PROJECT_ROOT"

    echo "=== Waiting for services to be healthy ==="
    for i in $(seq 1 30); do
        if docker compose -f "$COMPOSE_DIR/compose.yml" -f "$COMPOSE_DIR/compose.test.yml" --profile test ps --format json 2>/dev/null | python -c "
import sys, json
services = [json.loads(line) for line in sys.stdin if line.strip()]
healthy = sum(1 for s in services if s.get('Health', '') == 'healthy')
print(f'{healthy}/{len(services)} healthy')
if healthy >= 2:
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
            break
        fi
        echo "  Waiting... ($i/30)"
        sleep 3
    done

    echo "=== Running Alembic migrations ==="
    docker compose -f "$COMPOSE_DIR/compose.yml" -f "$COMPOSE_DIR/compose.test.yml" --profile test run --rm migrate
fi

echo "=== Running pytest ==="
case "$ACTION" in
    unit)
        pytest tests/unit/ -x -q
        ;;
    integration)
        DATABASE__URL="postgresql+asyncpg://app:app-local-only@localhost:5432/stock_intelligence" \
        pytest tests/integration/ -x -v
        ;;
    all)
        pytest tests/unit/ -x -q
        DATABASE__URL="postgresql+asyncpg://app:app-local-only@localhost:5432/stock_intelligence" \
        pytest tests/integration/ -x -v
        ;;
esac

echo "=== All tests passed ==="
