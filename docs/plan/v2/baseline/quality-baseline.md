# Baseline de qualidade

Data local: 2026-07-18  
Commit de referência: `2b097ef229e095c006223ffaa745bd1c93aedac6`  
Python: `3.12.7`

## Resultados locais

| Verificação | Resultado | Observação |
| --- | --- | --- |
| `pytest --collect-only -q` | 98 testes no baseline original | Antes das fixtures de F0-PR04 |
| `pytest -q` | 105 aprovados em 3,59 s | Inclui 7 testes de integridade das fixtures |
| `ruff check .` | Aprovado | Sem erros nas regras configuradas |
| `ruff format --check .` | Falhou | 49 arquivos anteriores à Fase 1 requerem formatação |
| `python -m compileall -q src` | Aprovado | Imports compiláveis no ambiente local |
| `mypy src` | Falhou | 6 erros iniciais: aliases PEP 695, import do SDK e pacote `apps` ambíguo |
| Cobertura | 24% (3.256 statements, 2.488 ausentes) | Medida com `pytest-cov==6.0.0`; XML local em cache ignorado pelo Git |
| `pip-audit .` | Bloqueado localmente | Resolver de metadata do `litellm` tentou compilação sem Cargo; CI audita o requirements pinado exportado pelo `uv` |
| `detect-secrets --all-files` | Execução local inconclusiva | Cache e `.git` tornaram a primeira varredura lenta; workflow exclui diretórios ignorados e preserva código/config/docs |

## Política do gate inicial

Ruff lint, compileall, testes e integridade das fixtures são obrigatórios. Formatação e mypy ficam visíveis como checks informativos até a correção dos débitos em F1-PR01/F1-PR02; não podem ganhar novas falhas. Dependency audit e secret scan começam informativos para permitir triagem antes de serem promovidos a bloqueantes.

## Artefatos do CI

O workflow `.github/workflows/ci.yml` instala Python e dependências em ambiente limpo, executa jobs separados e publica por 30 dias:

- `ruff-check.txt` e `ruff-format.txt`;
- `mypy.txt`;
- `pytest.xml`, `coverage.xml` e `pytest-coverage.txt`;
- `pip-audit.json` e `detect-secrets.json`.

O primeiro run remoto deve ser anexado a este baseline antes de marcar “pipeline em clone limpo” e “métricas publicadas” como concluídos.
