# **Descoberta de novas ações**

O agente de captação de oportunidades não deve simplesmente perguntar ao LLM “qual ação comprar”.

O processo correto é:

1. Motor determinístico define o universo elegível.

2. Aplica liquidez, tamanho, histórico, cobertura e disponibilidade de dados.

3. Calcula fatores e rankings.

4. Detecta anomalias, mudanças e eventos.

5. Seleciona um conjunto pequeno de candidatos.

6. O agente produz um research brief.

7. O crítico tenta eliminar falsos positivos.

8. A ação entra em uma fila de pesquisa.

9. Somente após uma tese completa ela se torna candidata à carteira.

Estados possíveis:

``` uncovered screened research_queue under_research watchlist candidate portfolio reduce_candidate exit_candidate rejected

``` Registre também o motivo de cada mudança de estado.

# **Notícias: comparação com métricas e tese**

Para cada notícia, produza uma estrutura como:

```
 { "event_type": "guidance_revision", "direction": "negative", "materiality": 0.91, "novelty": 0.82, "source_quality": 0.94, "affected_metrics": [ "revenue_growth_2026", "ebitda_margin_2026" ], "thesis_conflict": true, "thesis_items_affected": [ "margin_expansion", "pricing_power" ], "impact_horizon": "3_12_months", "requires_recalculation": true }

``` Depois:

1. O motor busca os valores atuais das métricas afetadas.

2. Recalcula os cenários.

3. Verifica limites da tese.

4. Atualiza o risco.

5. Só dispara o comitê se a materialidade ultrapassar um limite.

Isso evita gerar uma recomendação para cada manchete.

# **RAG e embeddings**

Use RAG para recuperar trechos de:

DFP.

ITR.

FRE.
