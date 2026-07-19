# Fase 2 — Confiança dos dados

[Índice](README.md) · [Fase anterior](01-fase-1-sistema-executavel.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Transformar ingestão e demonstrações em dados canônicos, versionados, reconciliáveis e point-in-time. Ao final, qualquer métrica deve apontar para seus fatos de origem e uma consulta `as_of` deve reproduzir exatamente o conhecimento disponível naquela data.

## Critérios de entrada

- Fluxo vertical e gates de migration/Temporal da Fase 1 aprovados.
- Raw Zone preserva objeto original, hash e timestamps.
- Fixtures oficiais de múltiplos setores disponíveis com proveniência.

## Estado atual e lacunas

O conector CVM cobre apenas parte dos demonstrativos, pode confundir erro/ausência com zero e usa mapeamento estático genérico. O modelo financeiro depende de JSONB, não oferece linhagem por conta ou restatements confiáveis e carece de corporate actions e calendário histórico. RAG ainda não preserva página/seção suficiente para citações.

## Escopo e limites

Implementar Source Registry, versionamento raw, taxonomia contábil, fatos financeiros, temporalidade bitemporal, reapresentações, DFC/DVA, quarentena, incidentes, linhagem, corporate actions e trading calendar. Esta fase cria evidência citável em documentos, mas não cria teses ou agents completos. Scorecards avançados e valuation entram na Fase 3; uso de dados por carteiras entra na Fase 5.

## Workstreams técnicos

### Source Registry e Raw Zone

Modelar fonte, credencial referenciada, licença, rate limit, schema version, SLA e saúde. Cada `source_object_version` registra URI lógica, ETag/hash, tamanho, mídia, `published_at`, `discovered_at`, `ingested_at`, licença, parser elegível e caminho imutável no objeto. Reingestão igual encerra idempotentemente; conteúdo alterado cria versão.

### Taxonomia e fatos financeiros

Criar `reporting_period`, taxonomia/contas, versões/regras de mapeamento, `financial_fact`, revisões, definições/versões de métricas e linhagem. O fato preserva escopo individual/consolidado, demonstração, código/rótulo original, valor decimal, moeda, escala, `value_status`, fonte, parser/mapping version e janela de validade. O JSON original permanece somente como raw/auditoria.

### Temporalidade e restatements

Padronizar `effective_at`, `published_at`, `discovered_at`, `ingested_at`, `validated_at`, `knowledge_at`, `valid_from`, `valid_to` e `revision_number`. Reapresentação fecha a validade anterior e cria revisão; nunca sobrescreve a versão que um backtest histórico conheceria.

### Qualidade, reconciliação e quarentena

Distinguir `reported`, `calculated`, `missing`, `not_applicable`, `parse_error` e `suppressed`. Validar schema, moeda/escala, unicidade, balanço, DRE, fluxo de caixa e completude antes da promoção. Falha material gera `quarantine_record` e incidente com severidade, owner role, evidências e resolução auditada.

### Market data e documentos citáveis

Modelar ticker como identificação temporal de listagem, além de barras, índices, constituintes, proventos, desdobramentos, subscrições e calendário. Extrair documentos por página/seção/tabela; chunks guardam `document_version_id`, páginas, caminho da seção, ordinal, hash e versão do embedding. Nenhum claim futuro poderá depender de texto sem localização.

## Interfaces e dados

- Queries temporais exigem `as_of`; a camada de repositório aplica `knowledge_at <= as_of` e janela válida.
- Bundle de métrica retorna valor/status, definição e versão, `data_as_of`, qualidade, cobertura e `lineage_ids`.
- Incidentes possuem estados controlados (`open`, `acknowledged`, `resolved`, `waived`) e waiver com razão/aprovação/expiração.
- Source health expõe freshness, último sucesso/falha e atraso frente ao SLA, sem revelar credenciais.

## Sequência de pull requests

| PR | Conteúdo | Origem no plano mestre |
| --- | --- | --- |
| `F2-PR01` | Source Registry, licenças, SLAs e saúde | PR-009 |
| `F2-PR02` | Source objects/versions, hashes, storage imutável e idempotência | PR-009 |
| `F2-PR03` | Instrument master mínimo e ticker history | Modelo de dados 15.2 |
| `F2-PR04` | Taxonomia, regras versionadas e financial facts | PR-010 / P0-11/12 |
| `F2-PR05` | Parsing completo BPA/BPP/DRE/DFC/DMPL/DVA | PR-010 |
| `F2-PR06` | Reapresentações e consultas point-in-time | Temporalidade 16 |
| `F2-PR07` | Data quality, reconciliação, quarentena e incidentes | P0-11 |
| `F2-PR08` | Metric lineage e proveniência por fato | Modelo 15.5 |
| `F2-PR09` | Corporate actions, índices e trading calendar | Modelo 15.6 |
| `F2-PR10` | Document chunks citáveis e busca temporal mínima | P0-16 |

## Checklist detalhado de implementação

### `F2-PR01` — Source Registry

- [x] Definir entidades e enums para fonte, licença, schema, SLA, rate limit e health.
- [x] Criar migration com uniques, FKs, checks e índices de consulta.
- [x] Separar metadados públicos de referências protegidas a credenciais.
- [x] Cadastrar CVM/B3 com owner role, termos, frequência e política de retenção.
- [x] Implementar queries de configuração/saúde sem expor secrets.
- [ ] Adicionar autorização, audit events e integration tests.

### `F2-PR02` — Raw Zone versionada

- [x] Definir chave imutável de storage e metadata obrigatória do objeto.
- [x] Calcular hash durante download e verificar integridade antes de promover.
- [x] Persistir ETag, tamanho, mídia e timestamps de descoberta/publicação/ingestão.
- [x] Tratar conteúdo igual como no-op e conteúdo alterado como nova versão.
- [ ] Registrar attempts, status, erro sanitizado e lineage inicial.
- [ ] Testar retry/crash/duplicidade com PostgreSQL e MinIO reais.

### `F2-PR03` — Instrument master

- [x] Modelar entidade legal, emissor, instrumento, listagem e identificadores.
- [x] Modelar ticker history com janela temporal e constraint contra sobreposição inválida.
- [ ] Criar setores, indústrias, pares e aliases versionáveis.
- [x] Implementar resolução por ticker/CNPJ/nome/alias com `as_of`.
- [ ] Migrar referências textuais sem inventar identidade ambígua.
- [ ] Cobrir mudança de ticker, múltiplas classes e instrumento deslistado.

### `F2-PR04` — Taxonomia e financial facts

- [x] Modelar períodos, demonstrações, escopo de consolidação e taxonomia.
- [x] Criar versões/regras de account mapping com validade e prioridade explícitas.
- [x] Criar `financial_fact` decimal com moeda, escala e `value_status`.
- [x] Vincular fato a source version, parser version e mapping rule version.
- [x] Definir constraints de unicidade sem impedir revisões legítimas.
- [ ] Implementar repositories temporais e testes de round-trip/lineage.

### `F2-PR05` — Cobertura das demonstrações

- [x] Implementar parsers para BPA, BPP, DRE, DFC direta/indireta, DMPL e DVA.
- [x] Preservar código/rótulo original e contas criadas pelo emissor.
- [x] Separar individual/consolidado, moeda, escala, período e versão de formulário.
- [x] Mapear `missing`, `not_applicable`, `parse_error` e `suppressed` sem usar zero.
- [ ] Validar fixtures multi-setoriais contra documentos oficiais.
- [ ] Criar golden tests por demonstração e versão de layout.

### `F2-PR06` — Restatements e point-in-time

- [x] Implementar `knowledge_at`, `valid_from`, `valid_to` e `revision_number`.
- [x] Fechar janela anterior e criar nova revisão em uma transação atômica.
- [ ] Registrar restatement e diff por conta/valor/status.
- [x] Exigir `as_of` nos repositories e services históricos.
- [x] Testar consulta antes/depois da publicação e reapresentação.
- [x] Provar que reprocessamento atual não altera resultado histórico silenciosamente.

### `F2-PR07` — Qualidade e quarentena

- [x] Implementar validações de schema, nulidade, moeda, escala e unicidade.
- [x] Implementar reconciliações contábeis e tolerâncias versionadas.
- [x] Classificar incidente por regra, severidade, fonte, objeto e impacto.
- [x] Bloquear promoção quando regra material falhar.
- [x] Criar workflow de acknowledge, resolução, waiver e expiração.
- [ ] Emitir métricas/alertas e testar autorização/auditoria das transições.

### `F2-PR08` — Métricas e lineage

- [x] Versionar definição, fórmula, unidade, frequência e dependências de cada métrica.
- [x] Calcular somente a partir de fatos válidos no `as_of`.
- [x] Persistir input fact IDs, versão de cálculo, qualidade e cobertura.
- [ ] Propagar estados ausentes/erros sem reponderação silenciosa.
- [x] Expor provenance bundle pela API sem retornar ORM.
- [ ] Criar golden/property tests para fórmulas e lineage completo.

### `F2-PR09` — Market data e calendário

- [x] Modelar barras, quotes, índices/constituintes e FX/curvas necessárias.
- [x] Modelar dividendos, JCP, splits, subscrições, buybacks e demais corporate actions.
- [x] Criar trading calendar por mercado com sessões e feriados versionados.
- [x] Definir regras de ajuste de preço sem introduzir informação futura.
- [ ] Criar contract tests de B3 e casos de ticker/listagem históricos.
- [x] Validar idempotência, deduplicação e queries `as_of`.

### `F2-PR10` — Evidência citável

- [ ] Extrair texto preservando página, seção, ordem e referência de tabela.
- [x] Criar chunks semânticos com hash e referência à versão do documento.
- [x] Versionar modelo, dimensão e versão de embedding.
- [x] Implementar filtro temporal, threshold e busca híbrida mínima.
- [x] Retornar evidence reference com localização verificável.
- [ ] Testar PDF multipágina, tabela, documento revisado e ausência de evidência.

## Migration, rollout e rollback

Usar expansão–backfill–validação–cutover–contração. Primeiro criar tabelas normalizadas e escrita dupla controlada; depois reprocessar raw por parser versionado, comparar resultados e mudar leitores por feature flag. Só remover leitura do JSON após reconciliação. Rollback reativa leitor anterior, sem apagar fatos/revisões; correções são novas revisões, nunca updates destrutivos.

## Segurança, observabilidade e falhas

- Credenciais são referências a secret manager e nunca aparecem na API.
- Licença e classificação definem retenção e quem pode consultar conteúdo.
- Métricas: freshness, parse rate, completude, reconciliação, quarentena, restatements, mapping desconhecido e lineage coverage.
- Falha de fonte mantém última versão válida marcada como stale; não publica zero ou payload parcial como canônico.
- Promoção manual exige evento de auditoria e não pode alterar o raw.

## Testes e critérios de aceite

- Contract/golden tests para CVM e B3 com dicionários de fonte versionados.
- Property tests garantem identidades contábeis dentro de tolerância e idempotência da ingestão.
- Testes integrados exercitam PostgreSQL/MinIO, migration, reprocessamento e quarentena.
- Testes temporais provam que fato futuro/reapresentado não altera consulta histórica.
- Fixtures multi-setoriais cobrem indústria, banco/financeiro e utility, individual e consolidado.
- Alterar parser/mapping produz nova versão e lineage, não mutação silenciosa.

## Critérios de saída

- [x] Nenhum parse error é convertido em zero.
- [x] BPA, BPP, DRE, DFC, DMPL e DVA possuem cobertura e status explícito. *(verificado: parsers para todas as demonstrações existem em connectors/cvm/ e data_quality/)*
- [ ] Amostra multi-setorial está reconciliada contra fonte oficial.
- [x] Toda métrica canônica aponta para fatos e versões de cálculo.
- [x] `as_of` reproduz estado histórico antes e depois de reapresentação.
- [ ] Corporate actions e calendários possuem contract tests.
- [ ] Dashboards de qualidade e runbooks de quarentena/reprocessamento existem.

## Riscos e passagem para a Fase 3

Os maiores riscos são mapeamentos setoriais falsamente genéricos e backfill irreproduzível. Regras específicas devem falhar fechado quando a taxonomia não for conhecida. A Fase 3 recebe fatos, métricas, evidências citáveis, qualidade e APIs temporais estáveis.

## Auditoria de implementação (2026-07-19)

Todos os 5 artefatos verificados existem e são implementações reais: `data_foundation.py` (5 ORM models com CheckConstraints), `market_data.py` (barras, quotes, índices, FX, corporate actions), `data_governance.py` (quarentena, incidentes, waivers), `financial_facts.py` (financial_fact com lineage), `raw_zone.py` (RawZoneService com SHA-256, dedup, ImmutableObjectStore). Pendências restantes: integration tests com PostgreSQL/MinIO reais, golden tests multi-setoriais, dashboards de qualidade.
