# Integração do runtime de activities

## Por que existe uma porta explícita

O fluxo de candidato combina componentes que já pertencem a domínios diferentes do IA Investing:

- instrument master;
- source registry;
- conectores oficiais;
- armazenamento bruto;
- parsing e qualidade;
- agent runtime governado;
- research cases e teses;
- valuation;
- risco;
- comitê.

As activities Temporal não devem importar e acoplar todos esses serviços diretamente. O pacote usa `CandidateActivityRuntime` como porta tipada e `CallbackCandidateActivityRuntime` como adapter de composição.

Esse desenho evita:

- transações abertas durante chamadas externas;
- dependência circular entre domínio e infraestrutura;
- agents escrevendo diretamente em fatos canônicos;
- workflows impossíveis de testar;
- substituição silenciosa de serviços existentes.

## Bootstrap obrigatório

O pacote substitui o worker duplicado por um worker que usa o registry governado. Para ativar candidatos, configure:

```env
CANDIDATE_INTELLIGENCE_ENABLED=true
CANDIDATE_RUNTIME_FACTORY=ia_investing.integrations.candidate_runtime:create_runtime
```

A factory pode ser síncrona ou assíncrona e deve retornar uma única instância compatível. O bootstrap valida todos os métodos antes de iniciar o worker. A composição equivalente é:

```python
from ia_investing.orchestration.activities.candidate_intelligence import (
    CallbackCandidateActivityRuntime,
    configure_candidate_activity_runtime,
)

runtime = CallbackCandidateActivityRuntime(
    resolve_identity=resolve_identity_callback,
    discover_sources=discover_sources_callback,
    persist_sources=persist_sources_callback,
    validate_supplied_source=validate_supplied_source_callback,
    evaluate_readiness=evaluate_readiness_callback,
    validate_sources=validate_sources_callback,
    collect_documents=collect_documents_callback,
    validate_financials=validate_financials_callback,
    analyze_fundamentals=analyze_fundamentals_callback,
    analyze_risk=analyze_risk_callback,
    build_committee_pack=build_committee_pack_callback,
    complete_run=complete_run_callback,
    screen_universe=screen_universe_callback,
    explore_shortlist=explore_shortlist_callback,
    persist_suggestions=persist_suggestions_callback,
)
configure_candidate_activity_runtime(runtime)
```

A configuração falha se for executada duas vezes. Isso impede uma troca silenciosa de adapter dentro do mesmo processo.

## Contrato de cada callback

### `resolve_identity`

Deve:

- carregar candidato com filtro de organização;
- resolver ticker contra `Listing`, `Instrument`, `Issuer` e identificadores válidos em `data_as_of`;
- validar CNPJ e código CVM quando disponíveis;
- detectar ambiguidade de classe/listagem;
- atualizar `issuer_id`, `instrument_id`, nomes e identificadores;
- retornar `blocked=true` quando a identidade não for inequívoca;
- registrar evidência e timeline.

Não deve escolher arbitrariamente entre duas listagens.

### `discover_sources`

Deve usar duas camadas:

1. descoberta determinística em CVM, B3, cadastro do emissor, domínios previamente conhecidos, sitemap e links do site oficial;
2. agent `company_source_discovery` somente para classificar, relacionar e explicar resultados limitados ao conjunto recuperado.

O agent pode propor URL, mas não confirmar `official=true` por inferência isolada.

### `persist_sources`

Deve:

- normalizar URL;
- deduplicar por hash;
- preservar evidência;
- criar/atualizar gaps;
- manter a versão do candidato;
- publicar eventos pela outbox;
- ser idempotente por `analysis_run_id` e conteúdo.

### `validate_supplied_source`

Validação mínima:

O pacote fornece `ia_investing.platform.http.SafeHttpClient`. O callback deve recebê-lo por injeção e não pode usar `httpx`/`requests` diretamente para URLs fornecidas ou descobertas dinamicamente.

- esquema `https` em produção;
- host permitido por política;
- resolução DNS A e AAAA;
- rejeição de endereços privados, loopback, link-local, metadata e redes reservadas;
- revalidação após cada redirect;
- limite de redirects;
- limite de bytes;
- content type permitido;
- timeout total;
- TLS válido;
- associação entre domínio/conteúdo e a identidade do emissor;
- correspondência com CNPJ, nome, código CVM ou links cruzados oficiais;
- registro do método e evidência.

Uma fonte fornecida pelo usuário só recebe `official=true` após essa validação.

### `evaluate_readiness`

Deve aplicar `ReadinessEvaluator` e considerar:

- identidade;
- confiança mínima por tipo de fonte;
- oficialidade;
- lacunas abertas;
- estágio operacional;
- documentos atuais;
- qualidade de dados;
- pesquisa, risco e pack de comitê.

### `validate_sources`

Revalida fontes descobertas pelo agent. Uma URL inacessível deve virar `unreachable`; uma associação incorreta, `rejected`; uma fonte antiga, `stale`.

### `collect_documents`

Deve:

- usar fontes verificadas;
- buscar DFP, ITR, fatos relevantes, releases, apresentações, políticas e dados operacionais;
- calcular hash;
- preservar original em S3/MinIO;
- registrar `SourceObject` e versão;
- não repetir download idêntico;
- localizar período mais recente esperado;
- criar gaps quando o material necessário estiver ausente.

### `validate_financials`

Deve executar apenas regras determinísticas:

- parsing;
- status de valor separado de zero;
- individual versus consolidado;
- moeda e escala;
- reconciliação;
- reapresentações;
- linhagem;
- promoção ou quarentena.

### `analyze_fundamentals`

Deve criar ou atualizar um `ResearchCase`, executar capabilities governadas e registrar:

- fatos;
- inferências;
- claims;
- evidências;
- contradições;
- valuation;
- riscos da tese;
- invalidações;
- cobertura de evidência.

Cobertura insuficiente retorna `pending`, não aprovação.

### `analyze_risk`

Deve combinar regras quantitativas e parecer qualitativo. Hard limit gera `reject` ou `blocked`, sem override pelo LLM.

### `build_committee_pack`

Deve congelar versões dos inputs e produzir um pack. O agent pode recomendar, mas a decisão precisa seguir as políticas de comitê e aprovação humana configuradas.

### `complete_run`

Deve ser idempotente e atualizar:

- status da execução;
- decisão;
- resumo;
- blocker codes;
- IDs de research case, tese e comitê;
- estado do candidato;
- elegibilidade;
- timeline;
- outbox.

`approved_portfolio_eligible=true` não cria posição, versão de carteira ou ordem.

### `screen_universe`

Deve construir universo point-in-time e excluir:

- instrumentos inativos;
- restricted list;
- listagens inválidas;
- baixa liquidez;
- cobertura de dados insuficiente;
- candidato já ativo;
- ativo já excluído pelo mandato;
- ativos sem preço ou calendário confiável.

### `explore_shortlist`

O agent recebe somente a shortlist determinística. O output é rejeitado quando introduz ticker fora dela.

### `persist_suggestions`

Deve:

- validar scores;
- deduplicar;
- definir expiração;
- preservar snapshot de fontes;
- atualizar métricas da execução;
- registrar limitações;
- nunca promover automaticamente.

## Runtime e workers atuais

O branch público contém duas formas de registrar workers: um `registry.py` governado e mapas próprios em `apps/worker/main.py`. Antes de ativar este pacote, consolidar o worker real para usar `definitions_for(capability)` do registry único. Caso contrário, workflows registrados no registry podem não ser executados pelo processo efetivamente iniciado.

## Testes obrigatórios de runtime

- activity idempotency;
- worker restart durante download;
- timeout de agent;
- source validation com redirect para IP privado;
- URL fornecida incorreta;
- ausência de RI;
- CVM encontrada, RI ausente;
- documento mais recente ausente;
- restatement;
- pesquisa sem evidência;
- hard risk breach;
- decisão pending;
- replay Temporal após mudança de código;
- repetição da mesma ocorrência de schedule sem duplicar `exploration_run`.
