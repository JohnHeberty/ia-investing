# PENDENTE — Itens a Implementar

## Prioridade Alta

### 1. Integração com Broker (Paper Trading Engine)
- **Status**: Pendente
- **Descrição**: Conectar o sistema a um broker real ou engine de simulação para execução de ordens de paper trading.
- **Opções**:
  - CEI/B3 (API oficial — limitada)
  - XP Investimentos API
  - NuInvest API
  - Simulation engine (order book simulado)
- **Requisitos**: Validação de compliance antes da execução, cálculo de custos (corretagem, emolumentos, ISS, IOF)

### 2. Temporal Worker Ativo
- **Status**: Pendente
- **Descrição**: O worker do Temporal não está processando tasks. Precisa de um `temporal worker` rodando com as workflows e activities registradas.
- **Comando**: `uv run python -m apps.worker.main` ou `docker compose up worker`

### 3. Sinais Quantitativos em Tempo Real
- **Status**: Pendente
- **Descrição**: Engine de sinais (momentum, mean reversion, breakout, volume) rodando diariamente para gerar sinais de entrada/saída.
- **Fontes**: yfinance (histórico), indicadores técnicos (ta-lib ou pandas_ta)

### 4. Cache de Dados de Mercado
- **Status**: Pendente
- **Descrição**: Cache de preços e fundamentais no banco para evitar chamadas excessivas ao yfinance.
- **Estratégia**: Atualizar preços a cada 15 min durante horário de mercado, fundamentais diariamente.

## Prioridade Média

### 5. Dados Fundamentalistas Detalhados
- **Status**: Parcialmente implementado
- **Descrição**: yfinance retorna dados básicos. Falta:
  - Dados CVM (DRE, BP, DFC completos)
  - Consenso de analistas
  - Valuation DCF detalhado
  - Comportamento sazonal

### 6. Sistema de Alertas por Email/Webhook
- **Status**: Pendente
- **Descrição**: Notificar o gestor quando:
  - Breach de limite de risco
  - Stop loss atingido
  - Recomendação do agent
  - Dados stale

### 7. Relatórios Exportáveis (PDF)
- **Status**: Pendente
- **Descrição**: Gerar relatórios diário/semanal/mensal em PDF com:
  - Performance da carteira
  - Recomendações dos agents
  - Análise de risco
  - Histórico de operações

## Prioridade Baixa

### 8. Multi-tenant Real
- **Status**: Pendente
- **Descrição**: Suporte a múltiplas organizações com dados isolados.

### 9. Mobile App (React Native)
- **Status**: Pendente
- **Descrição**: App mobile para acompanhar carteiras e aprovar recomendações.

---

## Code Review — Debt Técnico (Identificado em 30/Jul/2026)

### 10. Decompor `[id]/page.tsx` (832 linhas)
- **Status**: Pendente
- **Descrição**: O componente de detalhe da carteira tem 832 linhas. Decompor em sub-componentes:
  - `PositionsTab` (tabela + edição inline)
  - `PerformanceTab` (gráfico echarts + resumo)
  - `RiskTab` (métricas + barras de exposição)
  - `AllocationTab` (pie chart + legenda)
  - `LimitsTab` (tabela de limites)
  - `ThesesTab` (placeholder)
  - `RecommendationsTab` (tabela de recomendações)
  - `AuditTab` (timeline de auditoria)

### 11. Migrar inline styles para classes CSS
- **Status**: Pendente
- **Descrição**: `portfolios/[id]/page.tsx` tem dezenas de `style={{ ... }}` inline. Migrar para classes CSS usando tokens do design system (`var(--surface)`, `var(--line)`, etc).

### 12. `performance_outlook` hardcoded no advisor
- **Status**: Pendente
- **Descrição**: `portfolio_advisor.py` linha 337 — `expected_return_12m: 0.08` é sempre 8% independente do portfolio. Calcular a partir dos scores reais ou momentum dos ativos.

### 13. `use-quality-incidents` usa `institutionalApi`
- **Status**: Pendente
- **Descrição**: O hook `use-quality-incidents.ts` usa `institutionalApi` (openapi-fetch) enquanto todos os outros hooks foram migrados para `fetch()` direto. Padronizar para `fetch()`.

### 14. N+1 query em `list_all()`
- **Status**: Pendente
- **Descrição**: `paper_portfolio.py:50-52` faz uma query de posições por portfolio. Com 50 portfolios são 51 queries. Fazer batch-fetch de todas as posições do org em uma query e agrupar em Python.

### 15. Decompor `rebalance/page.tsx` (603 linhas)
- **Status**: Pendente
- **Descrição**: Arquivo com múltiplos componentes inline (`ProposeForm`, `DriftTable`, `TradesTable`, `ProposalDetail`, `Timeline`). Separar em arquivos individuais.

### 16. Adicionar validação de input no edit form
- **Status**: Pendente
- **Descrição**: `portfolios/[id]/page.tsx` — `parseFloat(editForm.quantity)` pode retornar `NaN`. Validar antes de enviar ao backend.

### 17. Decompor `rebalance/page.tsx` — `ProposeForm` precisa de form estruturado
- **Status**: Pendente
- **Descrição**: `ProposeForm` exige JSON bruto para alocações-alvo. Criar form com inputs de ticker estruturados.
