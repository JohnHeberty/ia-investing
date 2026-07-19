Transcrições.

Apresentações.

Políticas.

Notícias.

Teses anteriores.

Não use o banco vetorial como fonte oficial dos números.

A arquitetura correta é:

```
 PostgreSQL relacional = fatos e métricas oficiais Object storage = documentos originais pgvector = localização de trechos relevantes Evidence table = vínculo entre conclusão e fonte

``` Cada chunk deve conter:

``` document_id document_version page section period issuer_id chunk_text embedding_model embedding_version

``` Ao trocar o modelo de embedding, não sobrescreva silenciosamente os vetores antigos.

# **Estratégia de modelos**

Use roteamento por custo e complexidade.

As documentações atuais da OpenAI listam a família GPT‑5.6 com variantes Sol, Terra e Luna. Uma configuração razoável seria:

**Luna:** classificação de notícias, deduplicação, extrações simples e alto volume.

**Terra:** análise regular de documentos e atualização de teses.

**Sol:** casos complexos, agente crítico e comitê de investimento.

 [Mantenha os nomes em configuração, não espalhados no código, porque modelos e preços mudam. (OpenAI Developers)](https://developers.openai.com/api/docs/models?utm_source=chatgpt.com)

Para redução de custo:

Use parser antes do LLM.

Não envie documentos completos quando somente três seções são relevantes.

Use embeddings e filtros metadata-first.

Use um modelo menor para triagem.

Acione o modelo mais forte apenas em exceções.

Mantenha instruções estáveis no início do prompt para aproveitar caching.

Use processamento em lote em análises não urgentes.

Defina orçamento de tokens por workflow.

 [A OpenAI oferece prompt caching e mecanismos de processamento em lote para redução de custo e latência em workloads adequados. (OpenAI Developers)](https://developers.openai.com/api/docs/guides/prompt-caching?utm_source=chatgpt.com)

# **Backtesting correto**

Este é um ponto onde muitos sistemas financeiros falham.

 **Requisitos mínimos**

Dados point-in-time.

Composição histórica do universo.

Empresas que foram deslistadas.

Mudanças de ticker.

Dividendos e juros sobre capital.

Desdobramentos e grupamentos.

Emissões e bonificações.

Reapresentação de demonstrações.
