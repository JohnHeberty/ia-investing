# ADR-004: Alembic como Único Mecanismo de Schema

**Status:** Aceito
**Data:** 2026-07-18
**Decisor:** John Heberty de Freitas

## Contexto

O repositório tem Alembic configurado (`alembic.ini`, `migrations/env.py`) mas não possui nenhuma migration versionada. O schema é criado via `Base.metadata.create_all()` em `database.core.init_db()`. Isso funciona para prototipagem mas é perigoso em produção: não rastreia mudanças, não suporta downgrades, não permite colaboração segura.

## Decisão

Adotar Alembic como único mecanismo de schema:

1. **Remover `create_all()`** — Substituir por `alembic upgrade head` no startup
2. **Gerar migration inicial** — A partir do schema atual (51 tabelas)
3. **Todas as mudanças de schema** — Devem ser migrations, não alterações manuais
4. **CI deve verificar** — `alembic check` para detectar drift
5. **Naming convention** — `%(year)4d%(month)02d%(day)02d_%(hour)02d%(minute)02d_<description>`

## Alternativas Consideradas

1. **Manter `create_all()`** — Rejeitado: sem downgrade, sem versionamento, sem colaboração.

2. **Django-style migrations** — Não aplicável: SQLAlchemy não tem ORM migration nativo como Django.

3. **SchemaSpy/diagramas manuais** — Complementar, não substituto. Migrations são a fonte de verdade.

## Consequências

- **Positivas:** Versionamento de schema, upgrades/downgrades, drift detection, collaboração segura, audit trail.
- **Negativas:** Overhead de gerar migrations para cada mudança, learning curve para time.
- **Mitigações:** CI com `alembic check`, naming convention clara, migration generator automático.

## Referências

- `alembic.ini` — configuração Alembic
- `migrations/env.py` — async migration runner
- `src/database/core.py` — `init_db()` com `create_all()` (a ser removido)
- `src/database/models/` — 51 tabelas para migration inicial
