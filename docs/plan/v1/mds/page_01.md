# **Recomendação principal**

O sistema deve ser construído como uma **plataforma orientada a eventos para pesquisa financeira, gestão de teses e decisão de portfólio**, e não como uma sequência livre de agentes conversando entre si.

A divisão ideal é:

1. **Serviços determinísticos** coletam dados, calculam métricas, validam demonstrações, executam backtests e otimizam carteiras.

2. **Agentes de IA** interpretam documentos, notícias, riscos, contradições e cenários.

3. **Um orquestrador** inicia, pausa, repete e acompanha os processos.

4. **Um motor de políticas** decide o que pode continuar automaticamente e o que exige aprovação humana.

5. **Todas as conclusões** precisam apontar para fontes, versões dos dados e critérios de decisão.

O agendador deve iniciar o trabalho; o agente não deve “acordar sozinho”, navegar livremente pela internet e escrever diretamente no banco ou enviar uma ordem à corretora.

# **Arquitetura recomendada**

```
flowchart LR A[CVM / B3 / RI / BCB / IBGE / Notícias] --> B[Conectores de dados] B --> C[(Raw Zone<br/>S3 ou MinIO)] B --> D[Eventos e Orquestração<br/>Temporal] D --> E[Parsers determinísticos<br/>CSV / XBRL / HTML / PDF] E --> F[Validações de qualidade] F --> G[(PostgreSQL<br/>dados canônicos)]
G --> H[Motor de métricas] C --> I[Agente de documentos] C --> J[Agente de notícias] G --> K[Agente fundamentalista] H --> K I --> L[(Teses e evidências)] J --> L K --> L
 L --> M[Agente crítico] M --> N[Motor de risco] N --> O[Otimizador de carteira] O --> P[Comitê de investimento] P --> Q[Aprovação humana] Q --> R[Paper trading ou execução]
 D --> S[Tracing / Logs / Métricas / Evals] I --> S J --> S K --> S P --> S

``` **Os quatro planos do sistema**

**Plano de dados:** coleta, armazenamento, normalização, versionamento e qualidade.

**Plano de inteligência:** agentes especializados, RAG, interpretação de relatórios e análise de notícias.

**Plano de decisão:** scorecards, regras, risco, otimização de carteira e aprovação.

**Plano de controle:** agendamentos, eventos, retries, tracing, custos, permissões e auditoria.

Essa separação permite substituir um modelo de IA, uma fonte de dados ou um algoritmo de otimização sem reescrever todo o sistema.

# **Stack tecnológica sugerida**

|Componente|Minha escolha inicial|Por quê|Quando evoluir|
|---|---|---|---|
|Linguagem|Python|Ecossistema financeiro, IA, parsing, otimização e ciência<br>de dados|Manter Python; usar TypeScript apenas no front-<br>end|
|API|FastAPI + Pydantic|APIs tipadas e contratos estruturados para ferramentas<br>dos agentes|Separar serviços quando houver equipes ou<br>escalabilidade diferentes|
