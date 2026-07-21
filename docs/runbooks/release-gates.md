# Gates de release

## Bloqueios absolutos

Uma release não pode ser promovida quando qualquer item abaixo estiver presente:

- pacote local `agents` resolvendo no lugar do OpenAI Agents SDK;
- migrations pendentes ou não reversíveis na janela testada;
- worker sem activities registradas;
- scheduler em memória ativo;
- endpoint mutável sem autenticação, autorização, idempotência e auditoria;
- dado material sem origem e `knowledge_at`;
- recomendação material sem evidência;
- carteira com violação crítica sem waiver válido;
- solver com status diferente de `optimal`/`optimal_inaccurate` aceito sem política;
- backtest sem gate point-in-time;
- modelo/provider mock em produção;
- calibração política exclusivamente sintética;
- CI obrigatório ausente ou vermelho;
- secret scan com achado crítico;
- reconciliação de NAV/posição/caixa falha.

## Gate de PR

- `ruff format --check`
- `ruff check`
- `mypy` estrito para módulos alterados
- unit tests
- testes de arquitetura
- Alembic `upgrade head` e `check`
- frontend lint/test/build
- OpenAPI diff sem breaking change não versionada
- Temporal replay para workflows alterados
- agent eval para prompt/model/tool alterado
- dependency review

## Gate de staging

- E2E com PostgreSQL, MinIO e Temporal reais
- ingestão de fixture oficial versionada
- round-trip raw -> facts -> metric -> evidence -> thesis
- execução com provider real em conta não produtiva
- teste de expiração/retry/cancelamento de workflow
- teste de OIDC e permissões negativas
- teste de degradação de fonte
- teste de kill switch paper
- reconciliação diária
- observabilidade: logs, metrics e traces correlacionados

## Gate de produção

- change approval
- plano de rollback
- backup recente e restore testado
- migrations expand/contract
- release canário
- alertas e on-call definidos
- modelos/prompts aprovados no registry
- restricted list atualizada
- fontes e licenças válidas
- readiness financeira e regulatória aprovada
