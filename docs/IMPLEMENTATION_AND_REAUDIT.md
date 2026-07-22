# Implementação e nova auditoria — IA Investing

Data de referência: 22 de julho de 2026.

## 1. Escopo

Esta entrega revisa o branch público `main` e adiciona o domínio que ainda faltava para o fluxo solicitado: **candidato de investimento**.

O candidato não é sinônimo de emissor, instrumento, research case ou posição. Ele representa a proposta operacional de investigar uma ação para determinar se ela pode ser considerada por uma carteira.

O upgrade implementa:

- cadastro manual de ação;
- investigação automática;
- descoberta de fontes oficiais;
- lacunas bloqueantes;
- complemento humano;
- validação posterior da fonte;
- reanálise versionada;
- exploração autônoma;
- promoção controlada da oportunidade;
- API;
- banco;
- Temporal;
- interface;
- prompts;
- testes;
- aplicador conservador.

## 2. Situação atual do repositório público

O repositório avançou significativamente em relação à auditoria anterior. O branch público possui CI, migrations, frontend, modelos institucionais, agent runtime versionado, research, policy intelligence, carteiras-modelo, risk, paper execution, backtest e observabilidade.

Elementos relevantes já presentes:

- autenticação por sessão/OIDC, CSRF, security headers e rate limit;
- instrument master;
- raw/data foundation;
- financial facts point-in-time;
- research cases, evidências e claims;
- teses versionadas;
- valuation;
- mandatos e versões de carteira;
- risco institucional;
- paper trading;
- committee;
- portfolio ranking;
- Mission Control e páginas operacionais.

Portanto, a arquitetura não deve ser reiniciada. O caminho correto é integrar o novo domínio e corrigir inconsistências de runtime.

## 3. Lacuna de produto que permanecia

A tela de oportunidades existente cria diretamente um `ResearchCase` a partir de um identificador de instrumento. Isso pressupõe que:

- o instrumento já existe;
- a identidade já foi resolvida;
- as fontes são conhecidas;
- a cobertura documental é suficiente;
- o sistema sabe onde buscar relatórios;
- não há necessidade de intervenção humana durante onboarding.

Esse modelo não atende ao comportamento desejado de cadastrar apenas um ticker/nome e permitir que o ecossistema investigue o restante.

O novo fluxo adiciona uma camada anterior:

```text
Indicação ou descoberta
    -> candidato
    -> identidade
    -> fontes
    -> documentos
    -> dados
    -> research case/tese
    -> risco
    -> comitê
    -> elegibilidade
    -> carteira
```

## 4. Fluxo manual implementado

### 4.1 Cadastro

O usuário pode informar:

- ticker;
- bolsa;
- razão social, opcional;
- nome de negociação, opcional;
- CNPJ, opcional;
- código CVM, opcional;
- justificativa, opcional.

A API exige:

- organização autenticada;
- permissão;
- `Idempotency-Key`;
- `data_as_of` timezone-aware.

### 4.2 Criação inicial

O sistema cria:

- candidato com origem `manual`;
- execução número 1;
- lacunas de fonte padrão;
- evento de timeline;
- evento na outbox.

### 4.3 Resolução de identidade

O workflow deve resolver:

- listing válida no período;
- instrumento;
- emissor;
- classe da ação;
- CNPJ;
- código CVM;
- aliases e ticker histórico.

Ambiguidade bloqueia. O sistema não escolhe arbitrariamente.

### 4.4 Descoberta de fontes

Matriz padrão:

| Fonte | Nível | Confiança mínima |
|---|---|---:|
| Site oficial | required | 0,75 |
| Relações com investidores | blocking | 0,80 |
| Relatórios e resultados | blocking | 0,80 |
| Cadastro CVM | blocking | 0,90 |
| Documentos CVM | blocking | 0,90 |
| Listagem B3 | blocking | 0,90 |
| Governança | optional | 0,70 |
| Newsroom | optional | 0,70 |

A fonte precisa estar `verified`, possuir confiança mínima e ser oficial.

### 4.5 Falta de informação

Quando RI, página de resultados ou outra fonte bloqueante não é encontrada:

- o candidato vai para `awaiting_user_input`;
- a execução termina `blocked` ou `pending`;
- o gap permanece aberto;
- a UI mostra a ação requerida;
- nenhuma aprovação acontece;
- o usuário pode complementar.

### 4.6 Complemento humano

O usuário fornece URL usando `If-Match`.

A fonte é criada como:

```text
status = discovered
verification_method = user_confirmed
official = false
confidence = 0.70
```

Ela gera um workflow de validação. Só depois pode receber `verified`, `official=true` e resolver a lacuna.

### 4.7 Reanálise

Uma nova execução:

- recebe número incremental;
- preserva histórico;
- registra gatilho;
- usa novo `data_as_of`;
- não sobrescreve a execução anterior;
- não prossegue com blockers, salvo override operacional explícito.

### 4.8 Decisão

Resultados possíveis:

- `approve`;
- `reject`;
- `pending`;
- `watchlist`.

`approve` define elegibilidade, mas não cria posição.

## 5. Exploração autônoma implementada

### 5.1 Schedule

A interface permite criar Temporal Schedule com:

- nome;
- estratégias;
- liquidez mínima;
- quantidade máxima;
- intervalo de 24 a 720 horas;
- estado pausado ou ativo.

Políticas:

- overlap `SKIP`;
- catch-up limitado;
- pause-on-failure.

### 5.2 Universo determinístico

Antes do agent, devem ser removidos:

- instrumentos inativos;
- restricted list;
- baixa liquidez;
- baixa cobertura;
- exclusões explícitas;
- candidatos ativos existentes.

### 5.3 Shortlist

O screener determinístico produz uma shortlist limitada. O agent recebe somente essa shortlist.

Foi implementada uma proteção que descarta qualquer ticker que o agent tente introduzir fora do conjunto recebido.

### 5.4 Sugestões

Cada sugestão possui:

- instrumento e emissor;
- ticker e bolsa;
- score quantitativo;
- score de cobertura;
- score de descoberta de fontes;
- justificativa;
- sinais;
- riscos;
- snapshot de fontes;
- expiração;
- estado.

### 5.5 Promoção

A promoção:

- exige idempotência;
- verifica expiração;
- verifica duplicidade;
- cria candidato com origem `explorer`;
- cria gaps;
- cria execução;
- copia somente fontes válidas como descobertas;
- dispara a investigação completa.

### 5.6 Dispensa

A dispensa registra:

- timestamp;
- usuário;
- motivo.

O motivo não é misturado com riscos da ação.

## 6. Banco implementado

### `investment_candidates`

Identidade operacional do candidato, origem, estado, decisão, elegibilidade, organização, idempotência e controle otimista.

### `candidate_sources`

URLs normalizadas, hash, status, método, confiança, oficialidade, evidência e timestamps.

Constraints impedem:

- confiança fora de 0..1;
- status inválido;
- fonte verificada sem timestamp;
- agent inference confirmando oficialidade.

### `candidate_gaps`

Lacunas bloqueantes, requeridas e opcionais, com resolução auditável.

### `candidate_analysis_runs`

Execuções versionadas, gatilho, workflow, decisão, blockers e referências a research/tese/comitê.

### `exploration_runs`

Execuções autônomas, estratégia, universo, elegibilidade e parâmetros.

### `exploration_suggestions`

Sugestões, scores, expiração, promoção e dispensa.

### `candidate_events`

Timeline append-oriented do agregado.

## 7. API implementada

A API aplica:

- tenant scoping;
- permissões;
- idempotência;
- ETag/If-Match;
- status HTTP 202 para operações assíncronas;
- correlation ID;
- cursor tenant-scoped;
- outbox.

Foi corrigida uma vulnerabilidade de paginação encontrada durante a autoauditoria do pacote: o cursor agora só é carregado dentro da organização e usa desempate por UUID quando timestamps são iguais.

## 8. Temporal implementado

### Workflows

- `CandidateAnalysisWorkflow`;
- `CandidateSourceValidationWorkflow`;
- `AutonomousEquityExplorationWorkflow`;
- `ScheduledEquityExplorationWorkflow`;
- `CandidateOutboxDispatchWorkflow`.

### Retry

Políticas separadas:

- atividades rápidas;
- I/O de rede;
- agents.

### Idempotência

- IDs de workflow derivados de IDs persistidos;
- outbox publicada só após `start_workflow` bem-sucedido ou já existente;
- execução agendada usa `workflow_id` para não criar duas `exploration_runs` em retry.

### Bloqueio

O workflow encerra com checkpoint quando:

- identidade não resolve;
- fonte bloqueante falta;
- validação falha;
- documento atual falta;
- dados não são promovíveis;
- pesquisa não possui evidência;
- risco rejeita;
- comitê deixa pendente.

## 9. Frontend implementado

### Candidatos

- formulário manual;
- lista;
- status;
- origem;
- prontidão;
- decisão;
- elegibilidade.

### Dossiê

- checklist;
- identidade;
- fontes;
- gaps;
- runs;
- timeline;
- formulário de complemento;
- reanálise.

### Exploração

- execução manual;
- schedule;
- histórico;
- sugestões;
- scores;
- promoção;
- dispensa.

## 10. Prontidão

A prontidão da API agora considera:

- identidade;
- todas as fontes padrão;
- nível de cada requisito;
- confiança mínima;
- oficialidade;
- estágio operacional.

Ela não é usada como aprovação. É um indicador de completude.

## 11. Segurança aplicada pelo domínio

- source fornecida pelo usuário não é automaticamente oficial;
- agent inference não confirma oficialidade;
- URLs com credenciais são rejeitadas;
- transição direta para aprovado é proibida;
- agent explorer não amplia o universo;
- aprovação não cria posição;
- bloqueio não é convertido em zero ou fallback;
- concorrência otimista;
- organização em todas as queries de negócio;
- outbox para comandos duráveis.

## 12. Testes executados

### Python

```text
17 passed
```

Cobertura funcional:

- normalização de URL;
- rejeição de credenciais;
- proteção de oficialidade;
- blockers de fontes;
- liberação somente após verificação;
- criação manual;
- source fornecida permanece pendente;
- reanálise com blockers;
- state machine;
- explorer não introduz ativo fora da shortlist;
- rejeição de HTTP, credenciais em URL, localhost, metadata e IPs privados;
- allowlist de hosts e normalização segura de URL.

### Static compilation

- Python compileall aprovado.
- Migration compilada.
- Aplicador compilado.

### TypeScript

Sete arquivos TypeScript/TSX foram analisados pelo parser TypeScript 5.8.3 sem erros de sintaxe.

### Aplicador

Aplicação validada em repositório sintético:

- head Alembic detectado;
- migration instalada;
- modelos registrados;
- routers registrados;
- workflows e activities registrados;
- schedule inserido;
- navegação inserida;
- backups gerados.

## 13. O que está condizente no repositório atual

### Produto e frontend

O Mission Control já apresenta carteiras comparáveis, eventos materiais, funil de pesquisa, agents e qualidade. O domínio de carteiras institucionais contém mandatos, versões, snapshots, NAV, risco, otimização e backtests. A estrutura está alinhada com uma plataforma institucional.

### Dados

Existem instrument master, source objects, financial facts, lineage, policy intelligence e modelos de qualidade. A base conceitual está adequada.

### Agents

Existe runtime governado com artifacts, versions, tools, approvals, evals e tracing. O `RunAgentWorkflow` atual possui contrato rico com organização, capability, case, point-in-time e idempotência.

## 14. Bloqueadores ainda encontrados no branch público

### Correção incorporada — Dois registries de worker

O branch público possui um registry governado e, ao mesmo tempo, mapas próprios em `apps/worker/main.py`, com activities mock e bloqueio de provider real. O pacote substitui o worker por uma implementação que usa exclusivamente `definitions_for(capability)`.

A ativação de candidatos é feature-gated. Quando desabilitada:

- os workflows e activities de candidatos não entram no registry;
- o schedule não é criado;
- os routers retornam 503.

Quando habilitada, o startup exige `CANDIDATE_RUNTIME_FACTORY` e falha antes de aceitar trabalho caso a factory esteja ausente ou incompatível.

### P0-01 — Incompatibilidade em `AgentRuntimeService.create_run`

A activity governada chama `create_run(organization_id=...)`, mas a assinatura pública do serviço não aceita `organization_id`.

Risco:

- execução real do agent falha com `TypeError` antes de criar o run.

Correção:

- adicionar `organization_id` ao serviço e ao modelo, ou remover argumento somente se tenancy for derivada de outro objeto validado;
- organização deve participar da idempotência e de todas as queries;
- criar teste de activity com provider mock e banco real.

### P0-02 — Runtime do candidato precisa ser ligado

O pacote fornece porta e adapter callback, mas não pode escolher automaticamente quais serviços existentes devem criar research case, tese, risk e committee sem uma decisão explícita de integração.

Risco:

- workflow registrado sem runtime configurado falha de forma explícita.

Correção:

- implementar callbacks conforme `RUNTIME_WIRING.md`;
- configurar no startup;
- adicionar healthcheck usando `candidate_activity_runtime_configured()`;
- não iniciar worker se estiver ausente.

### Correção incorporada parcialmente — Cliente de egress seguro

O middleware público continua inadequado porque examina o host da requisição recebida e não controla requests de saída. O pacote adiciona `ia_investing.platform.http.SafeHttpClient`, com:

- HTTPS obrigatório por padrão;
- rejeição de credenciais embutidas;
- allowlist por domínio/sufixo;
- validação DNS A/AAAA antes de cada request e redirect;
- bloqueio de localhost, metadata e IPs não públicos;
- limite de redirects, bytes, tempo e content types;
- `trust_env=false`;
- testes unitários das políticas locais.

Risco residual P0:

- o cliente precisa ser adotado por todos os connectors e callbacks que aceitam URL dinâmica;
- DNS pode mudar entre validação e conexão. Produção ainda exige proxy/firewall de egress, bloqueio de redes privadas e testes de DNS rebinding;
- o middleware público deve ser removido ou renomeado para não sugerir proteção SSRF de saída.

### P0-04 — Source registry cria licença em toda chamada

`register_source` sempre instancia `SourceLicense`, usa `base_url=""` e não demonstra idempotência por código.

Risco:

- duplicidade de licença;
- falha por unique constraint;
- fonte sem base URL;
- configuração inconsistente.

Correção:

- upsert transacional de licença e fonte;
- validação de base URL;
- versionamento de terms;
- policy de retenção/licença separada da saúde da fonte.

### P0-05 — Schedule padrão ainda é limitado

Os defaults públicos cobrem outbox de operações, CVM condicional e paper. O pacote adiciona o dispatcher de candidatos de forma condicional; ele só aparece quando a feature está habilitada. A exploração recorrente específica é criada pela API e deve ser administrada como configuração por organização.

### P1-01 — Oportunidades ainda contém permissão mock

A página pública de oportunidades usa `usePermissions()` fixo. Isso não é aceitável para autorização real; UI não substitui backend, mas também não deve mostrar ações que o usuário não possui.

Correção:

- carregar permissions do contexto autenticado;
- ocultar/desabilitar comandos;
- manter enforcement no backend.

### P1-02 — Mission Control não mostra candidatos bloqueados

O painel já mostra research cases, mas deve adicionar:

- candidatos aguardando complemento;
- fontes pendentes de validação;
- execuções de exploração;
- sugestões próximas da expiração;
- SLA de investigação.

### P1-03 — Discovery oficial ainda precisa de adapters concretos

É necessário construir connectors reais para:

- CVM cadastro e documentos;
- B3 listing;
- site e RI;
- sitemap/RSS;
- redirects e domínios relacionados;
- histórico de mudanças de URL.

### P1-04 — Evals específicas

Adicionar datasets para:

- identificação de site de RI;
- classificação de página de resultados;
- associação domínio-emissor;
- detecção de falso positivo;
- gap corretamente emitido;
- exploração sem introduzir ativo externo.

### P1-05 — Auditoria append-only

`candidate_events` é append-oriented, mas banco ainda deve impedir UPDATE/DELETE por role/policy ou trigger em produção.

### P1-06 — Observabilidade operacional

Adicionar dashboards:

- candidates por estado;
- tempo por estágio;
- gaps por tipo;
- taxa de descoberta automática;
- taxa de complemento humano;
- validações rejeitadas;
- conversion explorer → candidate → approved;
- custo por candidato;
- evidência por decisão.

## 15. O que deliberadamente não foi implementado

### Ordem real

Nenhum caminho desta entrega envia ordem. Essa separação é intencional.

### Aprovação automática em carteira

A elegibilidade não modifica carteira. Mandato, otimização, risk e committee continuam necessários.

### Scraping livre

Não foi criada navegação irrestrita. Discovery deve operar por connectors e egress policy.

### Callback específico sem conhecer decisão de integração

A entrega não inventa como mapear todos os serviços existentes para cada activity. O contrato foi deixado explícito para evitar um adapter frágil e silenciosamente incorreto.

### Execução da stack original

O ambiente não conseguiu baixar o checkout Git por resolução DNS. A implementação foi validada isoladamente e em repositório sintético, mas o build completo, migrations reais, replay e E2E precisam ser executados no checkout local.

## 16. Ordem de merge recomendada

1. Corrigir `AgentRuntimeService.create_run`.
2. Consolidar worker registry.
3. Aplicar o upgrade e tornar `SafeHttpClient` obrigatório nos adapters de URL.
4. Construir callbacks do candidate runtime.
5. Aplicar migration em clone de banco.
6. Testar source discovery com fixtures e egress bloqueado.
7. Executar workflow e replay.
8. Executar frontend build/E2E.
9. Ativar schedule em paper environment.
10. Monitorar por período de burn-in.
11. Adicionar cards no Mission Control.

## 17. Gate de ativação

Não ativar exploração recorrente até:

- worker único;
- agent runtime funcional;
- egress seguro;
- source validator funcional;
- migration validada;
- replay aprovado;
- alerts configurados;
- budgets de agents configurados;
- permissions reais;
- paper environment claramente identificado.

## 18. Veredito final

A arquitetura pública está muito mais próxima da visão institucional e não precisa de reescrita. O maior gap funcional era o onboarding de uma ação desconhecida e o tratamento explícito de informação ausente. O pacote implementa esse domínio e o fluxo de exploração.

Ainda não é correto declarar o sistema integralmente pronto para produção porque os P0 de worker, agent runtime, egress e adapters precisam ser resolvidos e a stack completa precisa ser executada no repositório real.

O comportamento-alvo, após a integração, será:

```text
Usuário ou explorer indica ação
-> sistema resolve identidade
-> encontra e valida fontes oficiais
-> bloqueia e pede complemento quando necessário
-> usuário complementa
-> sistema valida e reprocessa
-> coleta documentos
-> valida dados
-> pesquisa com evidências
-> avalia risco
-> submete ao comitê
-> aprova, rejeita, mantém em watchlist ou deixa pendente
-> somente uma decisão posterior de carteira pode gerar posição
```
