# API e mapa de interface

## API de candidatos

### `POST /api/v1/investment-candidates`

Cria uma indicação manual e uma execução inicial.

Headers:

- `Idempotency-Key`: obrigatório;
- `X-Correlation-ID`: recomendado.

Query:

- `data_as_of`: timestamp timezone-aware.

Efeitos:

- cria `investment_candidate`;
- cria as lacunas padrão;
- cria `candidate_analysis_run` número 1;
- grava timeline;
- publica `candidate.analysis.requested` na outbox.

### `GET /api/v1/investment-candidates`

Lista candidatos da organização, com filtro de status e cursor tenant-scoped.

### `GET /api/v1/investment-candidates/{id}`

Retorna:

- candidato;
- fontes;
- lacunas;
- execuções;
- timeline;
- prontidão ponderada;
- bloqueios.

O header `ETag` contém `lock_version`.

### `POST /api/v1/investment-candidates/{id}/sources`

Adiciona uma fonte fornecida pelo usuário.

Headers:

- `If-Match`: obrigatório.

A fonte não é oficial até passar por `CandidateSourceValidationWorkflow`.

### `POST /api/v1/investment-candidates/{id}/gaps/{gap_id}/resolution`

Resolve uma lacuna. Uma lacuna bloqueante de fonte só pode ser resolvida quando existir uma fonte `verified`, `official=true` e do mesmo tipo.

### `POST /api/v1/investment-candidates/{id}/reanalysis`

Cria uma nova execução. Por padrão, bloqueios abertos impedem o comando. `allow_incomplete=true` é um mecanismo operacional explícito, não uma aprovação.

## API de exploração

### `POST /api/v1/exploration-runs`

Cria uma exploração sob demanda.

### `GET /api/v1/exploration-runs`

Lista histórico por organização.

### `GET /api/v1/exploration-runs/{id}`

Retorna execução e sugestões.

### `POST /api/v1/exploration-runs/suggestions/{id}/promotion`

Promove uma sugestão a candidato. Exige idempotência. O candidato recebe lacunas e uma execução completa; não entra em carteira.

### `POST /api/v1/exploration-runs/suggestions/{id}/dismissal`

Dispensa sugestão com motivo auditável separado da lista de riscos.

### `POST /api/v1/exploration-runs/schedules`

Cria um Temporal Schedule recorrente, entre 24 e 720 horas, com overlap `SKIP`, catch-up limitado e pause-on-failure.

## Interface

### `/opportunities/candidates`

- cadastro manual;
- lista por estado;
- origem manual/explorer;
- decisão e elegibilidade;
- acesso ao dossiê.

### `/opportunities/candidates/{id}`

Abas:

- visão geral;
- fontes;
- lacunas;
- análises;
- timeline.

Permite complementar URL e reprocessar após validação.

### `/opportunities/exploration`

- nova exploração;
- schedule recorrente;
- histórico;
- universo e elegibilidade;
- scores de cobertura;
- sinais e riscos;
- promoção;
- dispensa justificada.

## Estados do candidato

```text
suggested
  -> identity_resolution
  -> source_discovery
  -> awaiting_user_input | source_validation
  -> document_collection
  -> data_quality
  -> fundamental_analysis
  -> risk_analysis
  -> committee_review
  -> approved | rejected | watchlist | awaiting_user_input
```

Transições diretas de descoberta para aprovação são proibidas.
