# Baseline de segurança automatizada

Data: 2026-07-18

## Secret scan

`detect-secrets 1.5.0` foi executado sobre `src`, `tests`, `.github`, `.env.example`, `pyproject.toml`, Compose, Dockerfile e Alembic. Não foram encontrados tokens verificados, chaves privadas ou chaves de provedores. Foram reportadas três ocorrências com o mesmo hash:

| Arquivo | Tipo | Triagem |
| --- | --- | --- |
| `.env.example:2` | Basic Auth Credentials | Default local `postgres:postgres`; P1-07 |
| `alembic.ini:4` | Basic Auth Credentials | URL hardcoded; remover em F1-PR03 |
| `src/database/config.py:19` | Basic Auth Credentials | Default local; produção deve falhar fechado em F1-PR02 |

Esses achados não são secrets reais, mas representam defaults inseguros e não devem ser allowlisted permanentemente. O relatório deve ser preservado até a correção.

## Dependency audit

`pip-audit 2.10.1` foi iniciado diretamente contra o projeto. A resolução falhou antes da consulta de vulnerabilidades ao preparar metadata de `litellm`, que tentou usar Cargo/Rust no ambiente isolado. Portanto, não há resultado de vulnerabilidades local válido.

Execute localmente: resolva o grafo com `uv`, exporte versões pinadas e execute `pip-audit` contra o arquivo resultante. Falha de resolução continua visível e não pode ser interpretada como "zero vulnerabilidades".

## Próximas ações

- Corrigir os três defaults/URLs no início da Fase 1.
- Versionar `uv.lock` e repetir o audit local com `uv export`.
- Triar findings por severidade e promover dependency/secret scan a bloqueante.
