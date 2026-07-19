A consultoria profissional, independente e individualizada é regulada pela Resolução CVM 19 e depende de autorização. Em orientação publicada em 19 de janeiro de [2026, a CVM destacou deveres de compreender o perfil do cliente, analisar riscos, custos e vantagens e atuar no melhor interesse do investidor. (Serviços e Informações](https://www.gov.br/cvm/pt-br/assuntos/regulados/consultas-por-participante/consultores-de-valores-mobiliarios) [do Brasil)](https://www.gov.br/cvm/pt-br/assuntos/regulados/consultas-por-participante/consultores-de-valores-mobiliarios)

Antes de comercializar recomendações, publicar relatórios ou integrar ordens, será necessário revisar o produto com assessoria jurídica especializada em mercado de capitais.

 Caso sejam armazenados perfil de risco, patrimônio, posições ou outros dados pessoais, aplique LGPD. A ANPD observa que decisões automatizadas capazes de afetar
 [interesses do titular podem estar sujeitas a solicitação de revisão e conhecimento dos critérios utilizados. (Serviços e Informações do Brasil)](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-do-consumidor_como-proteger-seus-dados-pessoais-final.pdf/%40%40download/file?utm_source=chatgpt.com)

# **Estrutura recomendada do projeto**

```
 stock-intelligence/ ├── apps/ │  ├── api/ │  ├── worker/ │  ├── scheduler/ │  └── web/ ├── packages/ │  ├── domain/ │  ├── database/ │  ├── connectors/ │  │  ├── cvm/ │  │  ├── b3/ │  │  ├── investor_relations/ │  │  ├── macro/ │  │  └── news/ │  ├── parsers/ │  ├── normalization/ │  ├── data_quality/ │  ├── metrics/ │  ├── agents/ │  ├── workflows/ │  ├── portfolio/ │  ├── backtesting/ │  ├── evaluation/ │  └── observability/ ├── prompts/ │  ├── filing_analyst/ │  ├── news_analyst/ │  ├── critic/ │  └── committee/ ├── schemas/ ├── migrations/ ├── tests/ │  ├── unit/ │  ├── integration/ │  ├── golden_documents/ │  └── agent_evals/ ├── infra/ └── docker-compose.yml

```
Comece como **monólito modular**, com API e workers separados em processos, mas compartilhando domínio e banco. Microserviços prematuros só aumentariam deploys, tracing distribuído e problemas de consistência.

# **Roadmap recomendado**

 **Fase 1 — Fundação determinística**

Escopo:

20 a 50 ações líquidas.

CVM.

Cotações históricas B3.

Dados macro do Banco Central.

PostgreSQL.

Raw Zone.

Métricas financeiras.

Validações.

Dashboard básico.

Sem agentes e sem ordens reais.
