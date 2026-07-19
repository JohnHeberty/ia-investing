# Backlog priorizado do programa

Atualizado em 2026-07-18. O identificador permanece estável até o aceite. “Fase” indica o gate em que o item deve ser encerrado; itens transversais podem gerar tarefas em fases posteriores.

## P0 — Bloqueadores do plano mestre

| ID | Fase/PR principal | Dependências | Risco | Critério de aceite resumido |
| --- | --- | --- | --- | --- |
| P0-01 Namespace `agents` | F1-PR01 | ADR-001 | Runtime não inicia/import incorreto | SDK e pacote local importam isoladamente; compileall e import-mode passam |
| P0-02 Prompts | F1-PR01, F4-PR01 | Namespace | Agent falha ou usa contrato errado | Todo registro possui prompt/schema/hash/version e startup falha fechado |
| P0-03 Settings/dependências | F1-PR02 | Nenhuma | Ambiente irreproduzível | `uv sync --frozen` e check-config passam em clone limpo |
| P0-04 Migrations/create_all | F1-PR03 | Settings | Schema divergente/perda de dados | Banco vazio nasce por Alembic; upgrade/downgrade/check passam |
| P0-05 Mapeamento SQLAlchemy | F1-PR03 | Migration baseline | Campos não persistidos | Modelos tipados, autogenerate completo e round-trip JSONB passam |
| P0-06 Temporal activities | F1-PR05 | Contratos v1 | Workflow inexequível/duplicação | Workers registram activities; retry/replay/idempotência passam |
| P0-07 Scheduler | F1-PR06 | Workers | Agenda perdida | Temporal Schedules sobrevivem restart, pausam e aceitam backfill |
| P0-08 Contratos incompatíveis | F1-PR04 | Namespace | Defaults silenciosos corrompem análise | Um schema por mensagem e round-trip workflow/banco/API |
| P0-09 API/segurança/long jobs | F1-PR07, F5-PR01 | Identity baseline | Acesso indevido/bloqueio do event loop | OIDC/permissão/auditoria; long jobs retornam 202 e usam Temporal |
| P0-10 Filtro de setor | F1-PR07 | ORM tipado | Erro de runtime | Join, paginação e filtros combináveis passam em integração |
| P0-11 Integridade CVM | F2-PR05/07 | Raw Zone/taxonomia | Erro vira zero | Estados de valor distintos, demonstrações cobertas e reconciliação |
| P0-12 JSONB financeiro | F2-PR04/08 | Fatos/lineage | Sem PIT/auditoria por conta | Financial facts relacionais e métricas com lineage |
| P0-13 Domínio de carteira | F5-PR02/04 | Identity/dados PIT | Posição/NAV irreais | Mandato, versões, snapshots, caixa e NAV reproduzíveis |
| P0-14 Otimizador | F5-PR06 | Risco/inputs backend | Solução inválida apresentada como válida | Worker, feasibility e diagnóstico; sem fallback silencioso |
| P0-15 Backtest look-ahead | F5-PR07 | Market data PIT | Evidência econômica inválida | Suite anti-look-ahead e reprodução passam |
| P0-16 Evidência/RAG | F2-PR10, F3-PR02 | Document versions | Claim não citável | Chunk preserva página/seção/tabela e claim material exige evidence |
| P0-17 Observabilidade | F1-PR08, F4-PR06 | Infra/IDs | Incidente sem correlação | API/workers/connectors/agents correlacionados e dashboards ativos |
| P0-18 Infra local | F1-PR08 | Settings/migrations | Stack não reproduzível | Compose completo, versões fixas e healthchecks saudáveis |
| P0-19 Testes | Todas | Baseline local F0 | Regressões silenciosas | Gates específicos por fórmula, connector, workflow, prompt e frontend |
| P0-20 Licenciamento | F0-PR06, F9-PR02 | Evidência do titular | Redistribuição não autorizada | Direito comprovado ou conteúdo removido/substituído e histórico tratado |

## P1 — Débitos encontrados no baseline

| ID | Fase | Evidência atual | Aceite |
| --- | --- | --- | --- |
| P1-01 README desatualizado | F1 | Descreve `apps/`/`packages/`, mas código está em `src/` | Setup/estrutura/comandos refletem o repositório real |
| P1-02 Drift de formatação | F1-PR01 | `ruff format --check .`: 49 arquivos | Formatter passa e vira check obrigatório |
| P1-03 Type checking | F1-PR01/02 | `mypy src`: 6 erros iniciais | Strict mypy passa e vira check obrigatório |
| P1-04 Lock e ferramenta `uv` | F1-PR02 | `uv` ausente localmente e sem lock | Versão pinada, `uv.lock` versionado e sync frozen |
| P1-05 Cobertura baixa | F1–F5 | 24% em 3.256 statements | Baseline não regride e thresholds crescem por bounded context |
| P1-06 Código órfão | F1/F2 | 20+ modelos sem consumidor | Integrar, migrar ou remover com teste/import audit |
| P1-07 Defaults de desenvolvimento | F1-PR02 | Credenciais default em configuração/Compose | Produção falha sem secret e dev fica explicitamente isolado |
| P1-08 Exceções amplas/fallback vazio | F1/F2 | Connectors convertem falhas em vazio | Erros tipados, retry/quarentena e métricas sem silêncio |

## P2 — Melhorias não bloqueantes imediatas

| ID | Fase | Aceite |
| --- | --- | --- |
| P2-01 Padronizar documentação | F1 | Markdown/links/UTF-8 verificados |
| P2-02 Pin de actions por SHA | F1/F9 | Todas as third-party actions pinadas e atualizadas por processo controlado |
| P2-03 Renovação automatizada de dependências | F1 | Renovate/Dependabot abre PRs com changelog |
| P2-04 Métricas de duração/flakiness | F1 | Histórico por teste/job e quarentena com owner/expiração |
| P2-05 Developer CLI | F1 | Um comando verifica config, infra, migration e dependências |

## Regras de manutenção

- Fechar item somente anexando teste, relatório, migration ou decisão que prove o aceite.
- Débito reclassificado mantém o ID e registra justificativa/data.
- Exceção possui responsável por papel, condição de remoção e expiração.
- Finding novo de segurança, integridade financeira ou look-ahead nasce como P0 até triagem formal.
