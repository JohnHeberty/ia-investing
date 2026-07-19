Um score único opaco.

Agentes escrevendo SQL livremente.

Agentes acessando diretamente a corretora.

Backtest sem data real de publicação.

Métricas calculadas pelo LLM.

Decisões sem citações.

# **Combinação final que eu adotaria**

```
 Python FastAPI Pydantic Temporal OpenAI Agents SDK PostgreSQL pgvector S3 ou MinIO Parquet Polars DuckDB CVXPY OpenTelemetry Prometheus/Grafana MLflow Next.js Docker

```
A primeira versão deveria ser um **sistema de pesquisa com paper trading e aprovação humana**, cobrindo poucas ações, com dados oficiais da CVM/B3, métricas determinísticas e quatro agentes: coordenador, documentos, notícias e crítico/comitê.

A decisão arquitetural central é esta:

 **O workflow controla os agentes; os agentes não controlam o sistema. Os dados sustentam a decisão; o LLM interpreta os dados. O motor quantitativo calcula a** **carteira; o humano autoriza a ação.**
