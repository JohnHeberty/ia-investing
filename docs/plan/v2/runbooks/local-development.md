# Runbook de desenvolvimento local

## Pré-requisitos

- Git, Docker Desktop/Engine com Compose e Python conforme `.python-version`.
- `uv` na versão definida pelo workflow de CI.
- Cópia local de `.env.example` como `.env`; nunca versionar `.env`.

## Setup

```powershell
uv sync --all-extras --dev
Copy-Item .env.example .env
docker compose --profile dev up -d
```

O startup da API não cria tabelas. No Compose, o serviço `migrate` executa
`alembic upgrade head` antes da API e usa `DATABASE__URL`, a mesma configuração
do runtime. Fora do Compose, execute a migration manualmente.

## Migrations

```powershell
uv run alembic upgrade head
uv run alembic check
uv run alembic downgrade -1
uv run alembic upgrade head
```

Execute downgrade somente em banco local descartável ou após backup validado. A
migration inicial instala a extensão `vector`; o usuário do banco precisa ter
permissão para `CREATE EXTENSION`.

## Verificações

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q --cov=src --cov-report=term-missing
uv run python -m compileall -q src
```

No baseline F0, Ruff lint, compileall e testes passam; format e mypy possuem débitos registrados em `baseline/quality-baseline.md`.

## Diagnóstico

- API: `uvicorn apps.api.main:app --reload --app-dir src`.
- Serviços: `docker compose ps` e `docker compose logs <service>`.
- Configuração: comparar `.env.example` sem imprimir secrets.
- Temporal: usar a UI local na porta documentada no Compose.
- Banco: não executar `create_all`, DDL manual ou apagar volume para mascarar migration inválida.

## Recuperação

Pare a aplicação antes de alterar dependências ou migration. Preserve logs e o estado que reproduz a falha. Volumes só podem ser removidos quando o alvo local for confirmado e não houver dado necessário; prefira criar um ambiente de teste novo.
