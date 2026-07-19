|/16/26, 5:27 PM|Col2|Recomendação principal|Col4|
|---|---|---|---|
|**Componente**|**Minha escolha inicial**|**Por quê**|**Quando evoluir**|
|Orquestração|Temporal|Workflows duráveis, agendamentos, retries, estado<br>persistente e processos que podem pausar aguardando<br>aprovação|Temporal Cloud ou cluster próprio conforme<br>operação|
|Agentes|OpenAI Agents SDK|Ferramentas, agentes especializados, guardrails, sessões,<br>aprovações e tracing|LangGraph se independência de fornecedor e<br>grafos muito customizados forem prioritários|
|Banco<br>operacional|PostgreSQL|Dados financeiros relacionais, transações, JSONB,<br>particionamento e auditoria|Réplicas e particionamento avançado conforme<br>volume|
|Busca semântica|pgvector no PostgreSQL|Evita um banco vetorial separado no início|Banco vetorial dedicado apenas para corpus<br>realmente muito grande|
|Arquivos brutos|S3, Cloud Storage ou MinIO|Preservação dos relatórios originais e reprocessamento|Adicionar catálogo/lakehouse quando houver<br>grande volume|
|Arquivos<br>analíticos|Parquet|Formato colunar eficiente para histórico e backtesting|Iceberg/Delta somente quando precisar de<br>governança de lakehouse|
|Processamento|Polars + DuckDB|Análises locais rápidas, Parquet e baixo custo<br>operacional|Spark apenas quando o volume justificar|
|Transformações|SQL/dbt ou funções Python<br>versionadas|Métricas reprodutíveis e testáveis|Dagster se a linhagem de ativos de dados se<br>tornar central|
|Otimização|CVXPY|Alocação com limites, restrições de risco e turnover|Solvers comerciais se os problemas ficarem<br>grandes|
|Cache|Redis opcional|Cache, rate limit e locks curtos|Não deve ser a fonte definitiva dos dados|
|Eventos|Temporal Task Queues +<br>transactional outbox|Menos componentes no MVP|Kafka ou NATS quando houver muitos<br>consumidores independentes|
|Observabilidade|OpenTelemetry +<br>Prometheus/Grafana|Correlação de traces, métricas e logs|Plataforma gerenciada conforme equipe|
|Experimentos e<br>IA|MLflow + tracing dos agentes|Versionamento, avaliações, datasets de teste e<br>comparação de modelos|Plataforma corporativa conforme governança|
|Front-end|Next.js/React|Dashboard, aprovações, timeline e relatórios|Aplicativo móvel posteriormente|
|Implantação|Docker Compose em<br>desenvolvimento|Simplicidade|Kubernetes/ECS/Cloud Run quando houver<br>necessidade operacional real|

 Temporal foi desenvolvido para execução durável e recuperável, e seus Schedules permitem iniciar workflows recorrentes com políticas de sobreposição, backfill e
 [controle de falhas. Para esse caso, ele é mais adequado como orquestrador principal do que um cron simples. (Documentação Temporal)](https://docs.temporal.io/schedule?utm_source=chatgpt.com)

Dagster é especialmente forte em ativos de dados, linhagem, sensores e verificações de qualidade; Airflow é adequado para DAGs agendados de processamento em lote.
Eu não colocaria Temporal, Dagster e Airflow juntos no MVP: usaria Temporal e adicionaria Dagster apenas se a plataforma de dados crescer a ponto de justificar um [segundo orquestrador. (Dagster Docs)](https://docs.dagster.io/?utm_source=chatgpt.com)

 O Agents SDK é apropriado quando especialistas precisam de ferramentas, instruções, políticas, guardrails, handoffs ou aprovações diferentes. Para processos de backend, prefira o padrão **agentes como ferramentas**, no qual um coordenador continua controlando o workflow, em vez de handoffs livres entre agentes. A própria
 [documentação recomenda começar com um agente e criar especialistas somente quando houver mudança real de capacidade, política ou contrato. (OpenAI Developers)](https://developers.openai.com/api/docs/guides/agents?utm_source=chatgpt.com)

PostgreSQL suporta particionamento declarativo; pgvector adiciona busca vetorial com índices como HNSW e IVFFlat. Parquet é apropriado para históricos analíticos por [ser colunar e otimizado para armazenamento e leitura seletiva. (PostgreSQL)](https://www.postgresql.org/docs/current/ddl-partitioning.html?utm_source=chatgpt.com)

# **Fontes de dados**

 **Brasil**

 **Fontes primárias**

 **CVM**

Use a CVM como fonte principal para:

DFP: demonstrações financeiras anuais.

ITR: informações trimestrais.

FRE: formulário de referência.

FCA: dados cadastrais.

IPE: fatos relevantes, comunicados, avisos e demais documentos eventuais.

Informes de governança.

Histórico de documentos e reapresentações.
