(w): novos pesos.

(w_0): pesos atuais.

(\mu): retorno esperado por cenário.

(\Sigma): matriz de covariância.

(\lambda): aversão ao risco.

(c): custos, impostos e slippage.

Restrições possíveis:

```
 soma dos pesos = 100% peso por ativo <= 8% peso por setor <= 25% turnover <= 15% liquidez mínima obrigatória caixa entre 2% e 10% nenhuma compra em lista de restrição posição proposta <= percentual do volume médio risco total <= orçamento definido

```
 [CVXPY é uma linguagem Python para modelagem de problemas convexos e permite expressar objetivos e restrições dessa natureza de forma auditável. (Cvxpy)](https://www.cvxpy.org/tutorial/intro/index.html?utm_source=chatgpt.com)

O LLM pode ajudar a construir cenários e explicar a proposta. Ele não deve resolver informalmente a alocação.

# **Frequência dos workflows**

Não rode todos os agentes para todas as ações a cada hora.

|Use execução incremental e orientada a|materialidade.|
|---|---|
|**Workflow**|**Frequência ou gatilho**|
|Descoberta de documentos CVM/B3|A cada 10–30 minutos|
|Sites de RI|A cada 30–60 minutos ou RSS|
|Notícias gerais|A cada hora|
|Atualização de preços|Conforme licença e estratégia|
|Risco da carteira|Horário durante o mercado|
|Métricas de fechamento|Após o encerramento e consolidação|
|Atualização de tese|Quando houver informação material|
|Descoberta de novas ações|Semanal|
|Comparação de pares|Semanal|
|Simulação de rebalanceamento|Semanal ou por gatilho|
|Comitê completo|Semanal/mensal ou evento crítico|
|Reprocessamento histórico|Sob demanda|
|Avaliação dos agentes|Em cada mudança de prompt, modelo ou ferramenta|

 **Exemplo de workflow acionado por um novo ITR**

```
 filing.discovered -> download_document -> validate_hash -> archive_raw_document -> parse_structured_data -> normalize_accounts -> run_accounting_checks -> calculate_metrics -> compare_previous_periods -> run_filing_agent -> run_critical_agent -> update_thesis -> calculate_portfolio_impact -> decide_if_rebalance_required -> request_human_approval_if_material

``` Configure idempotência para que o mesmo evento não gere métricas duplicadas ou duas propostas de ordem.
