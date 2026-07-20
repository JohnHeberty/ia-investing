# ADR-003: Raw Zone Imutável e Fatos Canônicos Point-in-Time

**Status:** Aceito
**Data:** 2026-07-18
**Decisor:** John Heberty de Freitas

## Contexto

Dados financeiros são regenerados, corrigidos e reapresentados ao longo do tempo. A CVM publica versões corrigidas de DFPs, a B3 ajusta splits e dividendos, o BCB revisa séries macro. O sistema precisa preservar o estado original dos dados e rastrear quando cada versão foi obtida.

## Decisão

Implementar dois camadas de dados:

### Raw Zone (imutável)
- `raw_documents` — arquivo original com hash SHA-256, storage_path, http_etag, http_last_modified
- Dados brutos armazenados em MinIO/S3 com path `raw/{source}/{year}/{filename}`
- Nunca modificado após inserção; duplicatas detectadas por hash

### Fatos Canônicos (point-in-time)
- `financial_statements` — dados normalizados com `published_at` (quando ficou disponível)
- `financial_metrics` — métricas calculadas com `published_at`
- `market_prices` — preços com `trade_date`
- Cada registro vinculado ao `raw_document_id` de origem

### Normalização
- Pipeline em `src/normalization/` converte dados brutos em line_items canônicos
- Mapping de contas CVM em `_mappings.py` (CVM_ACCOUNT_MAP)
- Derived metrics em `_derived.py`

## Alternativas Consideradas

1. **Overwrite** — Sobrescrever dados ao atualizar. Rejeitado: perde histórico, impossível rastrear point-in-time.

2. **SCD Type 2 (Slowly Changing Dimensions)** — Versão completa com effective_from/effective_to. Rejeitado: complexo demais para dados que são reavaliados frequentemente.

3. **Append-only com flag de "mais recente"** — Considerado mas rejeitado:Raw Zone já resolve com hash, não precisa de flag.

## Consequências

- **Positivas:** Auditabilidade, rastreabilidade, detecção de duplicatas, suporte a backtesting point-in-time.
- **Negativas:** Mais storage, queries mais complexas (precisa filtrar por published_at), pipeline de normalização obrigatório.
- **Mitigações:** TTL para raw documents antigos, índices em published_at, compressão S3.

## Referências

- `src/database/models/data_foundation.py` — SourceLicense, DataSource, SourceSLA, SourceObject, SourceObjectVersion
- `src/database/models/financial_facts.py` — FinancialFact com knowledge_at/valid_from/valid_to
- `src/ia_investing/data/raw_zone.py` — RawZoneService com SHA-256 hash e ImmutableObjectStore
- `src/connectors/cvm/_financials.py` — parser CVM (DFP/ITR)
- `src/connectors/b3/_cotahist.py` — parser B3 COTAHIST
