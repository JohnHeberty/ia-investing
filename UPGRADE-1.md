# PLANO COMPLETO: Sistema de Investment Operations

## Visão do Operador

Um gestor profissional de carteiras de ações faz **centenas de micro-decisões** por dia. Cada decisão passa por um filtro: **Comprar? Vender? Manter? Aumentar? Reduzir?** O sistema precisa suportar **todo o ciclo de vida** dessa decisão, desde o sinal até a execução e pós-operação.

---

## WORKFLOW COMPLETO

### Ciclo de Vida da Carteira

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CICLO DE VIDA                                │
│                                                                     │
│  1. CRIAÇÃO → 2. MANDATO → 3. CONSTRUÇÃO → 4. MONITORAMENTO        │
│       ↓              ↓              ↓                ↓              │
│  Definir         Restrições    Seleção de       Acompanhar         │
│  objetivos       e limits      ativos           diariamente        │
│       ↓              ↓              ↓                ↓              │
│  5. ANÁLISE → 6. DECISÃO → 7. EXECUÇÃO → 8. PÓS-OPERAÇÃO          │
│       ↓              ↓              ↓                ↓              │
│  Sinal de        Comprar/      Ordem na        Performance         │
│  entrada/saída   Vender        bolsa           attribution         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## FASE 1: CRIAÇÃO DA CARTEIRA

### 1.1 Definição do Objetivo

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| Nome | Identificador único | "Fundo Brasil Long Only" |
| Objetivo | O que a carteira tenta fazer | "Superar Ibovespa em 3% a.a. com vol < 18%" |
| Benchmark | Referência de performance | Ibovespa, CDI+6%, S&P500 |
| Horizonte | Prazo médio das operações | Swing trade (5-30 dias), Position (30-180), Long-term (180+) |
| Mandato | Regras de investimento | Equity-only, max 20 posições, min 80% investido |
| Moeda | Moeda base | BRL, USD |
| Capital Inicial | Aporte inicial | R$ 10.000.000 |
| Gestor | Responsável | João Silva |

### 1.2 Restrições do Mandato

| Restrição | Tipo | Limite | Exemplo |
|-----------|------|--------|---------|
| Concentração por ativo | Hard | Máximo | 15% em um único ativo |
| Concentração por setor | Hard | Máximo | 25% em Petro & Gás |
| Concentração por emissor | Hard | Máximo | 20% em qualquer empresa |
| Posição mínima | Soft | Mínimo | 0.5% do NAV |
| Cash mínimo | Hard | Mínimo | 5% em caixa |
| Cash máximo | Soft | Máximo | 15% em caixa |
| Alavancagem | Hard | Máximo | 0% (proibido) |
| Derivativos | Hard | Máximo | 0% (proibido) |
| Turnover máximo | Soft | Mensal | 200% ao mês |
| Ativos elegíveis | Filter | Universo | B3 listing, min volume R$ 1M/dia |
| Short selling | Hard | Máximo | Proibido |
| ADRs/BDRs | Soft | Máximo | 10% do NAV |

### 1.3 Fluxo de Criação

```
Usuário preenche formulário
    ↓
Validação de regras de negócio
    ↓
Criação no backend (POST /model-portfolios)
    ↓
Status: draft
    ↓
Definição de mandato (opcional: selecionar existente)
    ↓
Criação de versão inicial (InstitutionalPortfolioVersion)
    ↓
Status: researching
```

---

## FASE 2: CONSTRUÇÃO INICIAL DA CARTEIRA

### 2.1 Screen de Universo

O gestor precisa definir **quais ativos são elegíveis**:

| Filtro | Critério | Justificativa |
|--------|----------|---------------|
| Listagem | B3 (BOVESPA) | Liquidez |
| Volume diário | > R$ 1M médio 20d | Capacidade de entrada/saída |
| Spread | < 0.5% | Custo de transação |
| Free float | > 15% | Governança |
| Segmento | Nível 1 ou 2 | Governança |
| Setor | Todos exceto FIN | Estratégia |
| Market cap | > R$ 2B | Estabilidade |

### 2.2 Scoring de Candidatos

Cada ativo do universo passa por **múltiplos scores**:

| Score | Fonte | Peso | Descrição |
|-------|-------|------|-----------|
| Fundamental | Agent `fundamentalist_analyst` | 30% | DRE, DCF, crescimento, qualidade |
| Momentum | Cálculo quantitativo | 25% | Preço relativo, volume, tendência |
| Valuation | Agent `fundamentalist_analyst` | 20% | P/E, EV/EBITDA, FCF yield |
| Risco | Agent `risk_director` | 15% | Volatilidade, beta, drawdown máximo |
| Sentimento | Agent `news` + `political` | 10% | Noticias, risco político |

### 2.3 Construção da Carteira

```
Listar candidatos com scores
    ↓
Otimização de portfólio (cvxpy)
    ↓
  - Maximizar retorno esperado
  - Restrições de mandato
  - Minimizar concentração
  - Maximizar diversificação
    ↓
Pesos sugeridos por ativo
    ↓
Validação de restrições
    ↓
Criação de versão (InstitutionalPortfolioVersion)
    ↓
Status: simulated
```

---

## FASE 3: MONITORAMENTO CONTÍNUO

### 3.1 Dashboard Diário (O que o gestor vê ao abrir o sistema)

| Seção | Dados | Formato |
|-------|-------|---------|
| **NAV** | Valor patrimonial, retorno diário, acumulado | KPI cards |
| **Posições** | Ticker, quantidade, preço, peso, P&L diário | Tabela ordenável |
| **Alocação** | Pie chart por ativo, bar chart por setor | Gráficos echarts |
| **Cash** | Saldo disponível, % do NAV | KPI card |
| **Risco** | VaR, volatilidade, drawdown, Sharpe | Gauge + tabela |
| **Alertas** | Violações de limite, breach de risco | Lista com badges |
| **Agent Runs** | Últimas análises executadas | Timeline |
| **Mercado** | Ibovespa, USD/BRL, Selic, VIX | Ticker bar |

### 3.2 Alertas Automáticos

| Tipo de Alerta | Trigger | Ação |
|----------------|---------|------|
| Breach de concentração | Ativo > 15% do NAV | Notificação + sugestão de redução |
| Breach de setor | Setor > 25% do NAV | Notificação + sugestão de realocação |
| Stop loss | Ativo caiu > 8% em 5 dias | Alerta de revisão |
| Take profit | Ativo subiu > 20% em 30 dias | Sugestão de lock de lucro |
| Liquidez | Volume caiu > 50% em 5 dias | Alerta de risco de saída |
| Risco | VaR > 2% do NAV | Notificação de excesso |
| Mandato | Cash < 5% | Alerta de compliance |
| Dados | Preço desatualizado > 4h | Alerta de stale data |

### 3.3 Reavaliação Periódica

| Frequência | Ação | Agent |
|------------|------|-------|
| Diária | Verificação de risco e limites | `risk_director` |
| Semanal | Reavaliação de teses vinculadas | `research_coordinator` |
| Quinzenal | Análise fundamentalista de posições | `fundamentalist_analyst` |
| Mensal | Análise macro e setorial | `macro` + `political` |
| Trimestral | Revisão completa com comitê | `investment_committee` |

---

## FASE 4: SINAIS DE ENTRADA/SAÍDA

### 4.1 Tipos de Sinal

| Sinal | Descrição | Fonte | Prioridade |
|-------|-----------|-------|------------|
| **BUY** | Comprar ativo não presente | Agent + Quant | Alta |
| **SELL** | Vender ativo presente | Agent + Quant | Alta |
| **INCREASE** | Aumentar posição | Agent + Quant | Média |
| **REDUCE** | Reduzir posição | Agent + Quant | Média |
| **HOLD** | Manter posição | Agent | Baixa |
| **EXIT** | Sair completamente | Stop/Target | Urgente |
| **REBALANCE** | Realocar pesos | Otimizador | Alta |

### 4.2 Geração de Sinais

```
┌─────────────────────────────────────────────────────────────────┐
│                    GERAÇÃO DE SINAIS                             │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  QUANTITATIVE │  │  FUNDAMENTAL │  │  MACRO/NEWS  │          │
│  │              │  │              │  │              │          │
│  │  - Momentum  │  │  - DCF       │  │  - Selic     │          │
│  │  - Mean Rev  │  │  - Scorecard │  │  - Inflação  │          │
│  │  - Breakout  │  │  - Growth    │  │  - PIB       │          │
│  │  - Volume    │  │  - Quality   │  │  - political │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └────────┬────────┘                 │                   │
│                  ↓                          │                   │
│         ┌────────────────┐                  │                   │
│         │   SCORE FINAL  │←─────────────────┘                   │
│         │   (ponderado)  │                                      │
│         └───────┬────────┘                                      │
│                 ↓                                               │
│         ┌────────────────┐                                      │
│         │   FILTROS      │                                      │
│         │  - Mandato     │                                      │
│         │  - Risco       │                                      │
│         │  - Liquidez    │                                      │
│         └───────┬────────┘                                      │
│                 ↓                                               │
│         ┌────────────────┐                                      │
│         │   SINAIS       │                                      │
│         │   FINAIS       │                                      │
│         └────────────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Critérios de Entry/Exit (Swing Trade)

| Critério | Entry (Compra) | Exit (Venda) |
|----------|----------------|--------------|
| **Momentum** | Preço > SMA20 e SMA20 > SMA50 | Preço < SMA20 ou SMA20 < SMA50 |
| **Volume** | Volume > 1.5x média 20d | Volume < 0.5x média 20d |
| **RSI** | RSI < 30 (sobrevendido) | RSI > 70 (sobrecomprado) |
| **MACD** | MACD cruzou acima da signal | MACD cruzou abaixo da signal |
| **Fundamental** | Score > 0.7 e P/E < média setor | Score < 0.4 ou P/E > 2x média |
| **Risco** | Beta < 1.5 e Vol < 30% | Beta > 2.0 ou Vol > 40% |
| **Liquidez** | Avg volume > R$ 5M/dia | Avg volume < R$ 1M/dia |

---

## FASE 5: DECISÃO E APROVAÇÃO

### 5.1 Fluxo de Decisão

```
Sinal gerado pelo Agent
    ↓
Apresentação no dashboard (card de recomendação)
    ↓
Gestor revisa:
  - Tese de investimento
  - Evidence do agent
  - Impacto no risco da carteira
  - Custo da operação
    ↓
Decisão: Aprovar / Rejeitar / Modificar
    ↓
Se Aprovar → Criar Ordem
Se Rejeitar → Registrar motivo
Se Modificar → Ajustar e reavaliar
    ↓
Approval Workflow (se mandato exigir):
  - 4-eyes: Outro gestor aprova
  - Risk officer aprova (se risco > limite)
    ↓
Ordem criada
```

### 5.2 Card de Recomendação (UI)

```
┌─────────────────────────────────────────────────────────┐
│ 🟢 COMPRA - PETR4                          Confiança: 85% │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Preço atual: R$ 38,50    Target: R$ 44,20  (+14.8%)   │
│  Stop loss: R$ 35,00      Risco: -9.1%                 │
│  Risk/Reward: 1.63                                       │
│                                                         │
│  Tese: Petróleo em tendência de alta, empresa com       │
│  DRE forte, P/E atrativo vs peers.                      │
│                                                         │
│  Evidence:                                               │
│  📄 [Fundamental] DRE Q3: Lucro +22% YoY               │
│  📰 [News] Petrobras anuncia investimento em refino     │
│  🌍 [Macro] OPEE corta produção, preços sustentados     │
│                                                         │
│  Impacto na carteira:                                    │
│  Setor: Petro & Gás 15% → 18% (limite: 25%) ✅         │
│  VaR: 1.2% → 1.4% (limite: 2%) ✅                      │
│  Cash: 8% → 3% (mínimo: 5%) ⚠️                         │
│                                                         │
│  [Aprovar] [Rejeitar] [Modificar] [Ver Análise Completa]│
└─────────────────────────────────────────────────────────┘
```

---

## FASE 6: EXECUÇÃO

### 6.1 Tipos de Ordem

| Tipo | Descrição | Uso |
|------|-----------|-----|
| **Market** | Executa agora, preço atual | Urgente, stop loss |
| **Limit** | Executa no preço especificado | Entrada planejada |
| **Stop** | Executa quando atinge preço | Proteção |
| **Stop Limit** | Stop + Limit combinado | Proteção com controle |
| **TWAP** | Execução ao longo do dia | Grandes quantias |
| **VWAP** | Execução ponderada por volume | Minimizar impacto |

### 6.2 Fluxo de Execução

```
Ordem criada
    ↓
Validação de compliance:
  - Saldo disponível
  - Limite de concentração
  - Horário de mercado
  - Day trade permitido?
    ↓
Envio para corretora (API B3/CEI)
    ↓
Execução parcial ou total
    ↓
Atualização de posição:
  - Position.quantity += order.quantity
  - Position.avg_cost = weighted average
  - Transaction registrada
    ↓
Cálculo de custos:
  - Corretagem (0.03%)
  - Emolumentos (0.03%)
  - ISS (0.05%)
  - IOF (0.38% day trade)
    ↓
Publicação de NAV
    ↓
Registro de auditoria
```

---

## FASE 7: PÓS-OPERAÇÃO

### 7.1 Performance Attribution

| Métrica | Cálculo | Frequência |
|---------|---------|------------|
| **Retorno total** | (NAV_final / NAV_inicial) - 1 | Diário |
| **Retorno vs benchmark** | Retorno_carteira - Retorno_benchmark | Diário |
| **Contribuição por ativo** | Peso × Retorno_ativo | Diário |
| **Contribuição por setor** | Soma dos ativos do setor | Semanal |
| **Sharpe ratio** | (Retorno - Risk_free) / Volatilidade | Mensal |
| **Sortino ratio** | (Retorno - Risk_free) / Downside_vol | Mensal |
| **Max drawdown** | Maior pico para vale | Contínuo |
| **Calmar ratio** | Retorno / Max_drawdown | Mensal |
| **Hit rate** | % de trades lucrativos | Mensal |
| **Win/Lucro avg** | Lucro médio / Prejuízo médio | Mensal |
| **Turnover** | Volume negociado / NAV | Mensal |
| **Cost ratio** | Custos totais / NAV | Mensal |

### 7.2 Análise de Pós-Mortem

```
Trade finalizado (posição zerada)
    ↓
Análise retrospectiva:
  - Entry price vs Entry signal
  - Exit price vs Exit signal
  - Tempo de permanência
  - Custo total da operação
  - Retorno líquido
    ↓
Classificação:
  - 🟢 Win: Retorno > 0
  - 🔴 Loss: Retorno < 0
  - ⚪ Scratch: |Retorno| < custos
    ↓
Aprendizado:
  - O sinal de entry estava certo?
  - O timing de exit foi bom?
  - O position sizing foi adequado?
  - O risco/reward foi respeitado?
    ↓
Salvo em: TradeJournal
    ↓
Feed para melhoria dos agents
```

### 7.3 Relatórios

| Relatório | Conteúdo | Frequência |
|-----------|----------|------------|
| **Diário** | NAV, posições, P&L, alertas | Diário |
| **Semanal** | Performance, mudanças, outlook | Semanal |
| **Mensal** | Atribuição, risco, compliance | Mensal |
| **Trimestral** | Análise completa, comitê | Trimestral |
| **Anual** | Review, taxas, benchmark | Anual |

---

## TELAS DO SISTEMA

### Tela 1: Dashboard Principal (`/`)

```
┌─────────────────────────────────────────────────────────────────────┐
│  📊 MISSION CONTROL                                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ NAV      │ │ Retorno  │ │ Sharpe   │ │ Posições │              │
│  │ R$ 12.3M │ │ +8.2%    │ │ 1.45     │ │ 18       │              │
│  │ +0.3% 🟢 │ │ vs +5.1% │ │ Acima    │ │ 85%      │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│                                                                     │
│  ┌─────────────────────────┐ ┌─────────────────────────┐           │
│  │  CURVA DE PERFORMANCE   │ │  ALOCAÇÃO POR SETOR     │           │
│  │  📈 [echarts line]      │ │  🥧 [echarts pie]       │           │
│  │  Carteira vs Ibovespa   │ │  Tech 30%, Finance 25%  │           │
│  └─────────────────────────┘ └─────────────────────────┘           │
│                                                                     │
│  ┌─────────────────────────┐ ┌─────────────────────────┐           │
│  │  RECOMENDAÇÕES PENDENTES│ │  ALERTAS ATIVOS         │           │
│  │  🟢 COMPRA PETR4  85%   │ │  ⚠️ VaR approaching     │           │
│  │  🔴 VENDA BBAS3   72%   │ │  ⚠️ Setor Tech > 25%    │           │
│  │  🟡 REDUZ VALE3   68%   │ │  ℹ️ Dados PETR4 stale   │           │
│  └─────────────────────────┘ └─────────────────────────┘           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  POSIÇÕES                                                   │   │
│  │  Ticker  Qtd    Preço    Peso    P&L diário   P&L total    │   │
│  │  PETR4   1.000  R$38.50  12.5%   +2.1%        +15.3%       │   │
│  │  VALE3   500    R$68.20  11.0%   -1.3%        +8.7%        │   │
│  │  ITUB4   2.000  R$33.10  10.8%   +0.5%        +12.1%       │   │
│  │  ...                                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Tela 2: Detalhe da Carteira (`/portfolios/[id]`)

```
┌─────────────────────────────────────────────────────────────────────┐
│  ← Voltar    FUNDO BRASIL LONG ONLY              [Editar] [Ações]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [Visão Geral] [Posições] [Performance] [Risco] [Teses]            │
│  [Recomendações] [Rebalance] [Auditoria]                           │
│                                                                     │
│  ┌─ VISÃO GERAL ──────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  NAV: R$ 12.3M  │  Retorno YTD: +8.2%  │  Sharpe: 1.45   │    │
│  │  Benchmark: Ibovespa  │  Excesso: +3.1%  │  Max DD: -4.2% │    │
│  │                                                             │    │
│  │  Mandato: Long Only  │  Moeda: BRL  │  Ambiente: Paper   │    │
│  │  Gestor: João Silva  │  Criado: 01/01/2026                  │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ POSIÇÕES ─────────────────────────────────────────────────┐    │
│  │  [Filtrar por setor] [Ordenar por P&L] [Exportar]          │    │
│  │                                                             │    │
│  │  Ticker  Nome         Qtd     Preço     Peso   P&L    %    │    │
│  │  PETR4   Petrobras    1.000   R$38.50   12.5%  +15.3% 🟢  │    │
│  │  VALE3   Vale         500     R$68.20   11.0%  +8.7%  🟢  │    │
│  │  ITUB4   Itaú         2.000   R$33.10   10.8%  +12.1% 🟢  │    │
│  │  MGLU3   Magazine     3.000   R$12.80   7.8%   -5.2%  🔴  │    │
│  │  WEGE3   WEG          800     R$42.30   6.9%   +3.1%  🟢  │    │
│  │  ...                                                        │    │
│  │                                                             │    │
│  │  ┌─ ALOCAÇÃO ─────────┐  ┌─ EXPOSIÇÃO SETOR ──────────┐  │    │
│  │  │ [echarts pie]       │  │ [echarts bar]               │  │    │
│  │  │ Top 5: 48%          │  │ Tech 30% | Fin 25% | ...   │  │    │
│  │  └────────────────────┘  └─────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ PERFORMANCE ───────────────────────────────────────────────┐    │
│  │  Período: [1M] [3M] [6M] [1Y] [YTD] [ALL]                 │    │
│  │                                                             │    │
│  │  [echarts line chart]                                       │    │
│  │  ━━━ Carteira    ─── Ibovespa    ··· CDI                   │    │
│  │                                                             │    │
│  │  Retorno    │ CAGR  │ Sharpe │ Sortino │ Calmar │ Max DD  │    │
│  │  +8.2%      │ 12.1% │ 1.45   │ 1.82    │ 2.90   │ -4.2%  │    │
│  │  vs +5.1%   │ 7.3%  │ 0.89   │ 1.01    │ 1.45   │ -5.0%  │    │
│  │                                                             │    │
│  │  [echarts waterfall] Decomposição de retorno                │    │
│  │  Seleção: +4.1% │ Alocação: +1.2% │ Custos: -0.3% │ ...   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ RISCO ─────────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  ┌─ GAUGE ─────┐  ┌─ LIMITES ──────────────────────────┐  │    │
│  │  │  Risco:     │  │  Limite      Valor     Status       │  │    │
│  │  │  MÉDIO      │  │  VaR 95%     1.4%      ✅ < 2%     │  │    │
│  │  │  [echarts]  │  │  Volatilidade 16.2%    ✅ < 20%    │  │    │
│  │  │             │  │  Max DD      -4.2%     ✅ < -10%   │  │    │
│  │  └─────────────┘  │  Setor Max   30% Tech  ✅ < 35%    │  │    │
│  │                    │  Concentração 12.5% PETR ✅ < 15%  │  │    │
│  │                    └─────────────────────────────────────┘  │    │
│  │                                                             │    │
│  │  [echarts radar] Exposição por fator                        │    │
│  │  Market: 0.85 │ Size: 0.32 │ Value: 0.45 │ Momentum: 0.67│    │
│  │                                                             │    │
│  │  [echarts waterfall] Stress testing                         │    │
│  │  Crash -30%: -18% │ Selic +5%: -3% │ Oil +50%: +2%       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ RECOMENDAÇÕES ────────────────────────────────────────────┐    │
│  │  [Todas] [Pendentes] [Aprovadas] [Rejeitadas]             │    │
│  │                                                             │    │
│  │  ┌─────────────────────────────────────────────────────┐   │    │
│  │  │ 🟢 COMPRA WEGE3                    Confiança: 78%   │   │    │
│  │  │ Preço: R$42.30 │ Target: R$48.00 (+13.5%)          │   │    │
│  │  │ Stop: R$38.00  │ R/R: 1.82                          │   │    │
│  │  │ Tese: Empresa líder em elétrica, crescimento estável│   │    │
│  │  │ [Aprovar] [Rejeitar] [Ver Análise]                  │   │    │
│  │  └─────────────────────────────────────────────────────┘   │    │
│  │                                                             │    │
│  │  ┌─────────────────────────────────────────────────────┐   │    │
│  │  │ 🔴 VENDA MGLU3                    Confiança: 82%   │   │    │
│  │  │ Preço: R$12.80 │ Target: R$10.50 (-18.0%)          │   │    │
│  │  │ Tese: Deterioração de margens, concorrência forte   │   │    │
│  │  │ [Aprovar] [Rejeitar] [Ver Análise]                  │   │    │
│  │  └─────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ HISTÓRICO DE OPERAÇÕES ───────────────────────────────────┐    │
│  │  Data       Tipo   Ticker  Qtd    Preço    P&L     Status │    │
│  │  15/01/2026 COMPRA PETR4   1.000  R$35.20  —       ✅     │    │
│  │  12/01/2026 VENDA  BBDC3   500    R$28.50  +5.2%   ✅     │    │
│  │  10/01/2026 COMPRA VALE3   500    R$62.10  —       ✅     │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Tela 3: Análise de Candidato (`/opportunities/candidates/[id]`)

```
┌─────────────────────────────────────────────────────────────────────┐
│  ← Voltar    PETR4 - PETROBRAS                   [Adicionar]       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [Resumo] [Fundamental] [Técnico] [Risco] [Valuação] [Notícias]   │
│                                                                     │
│  ┌─ RESUMO ───────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  Preço: R$38.50  │  Mkt Cap: R$250B  │  Setor: Energia   │    │
│  │  P/E: 5.2x       │  P/B: 1.1x        │  Div Yield: 8.5%  │    │
│  │  Beta: 1.35      │  Vol: 28%         │  Avg Vol: R$ 800M  │    │
│  │                                                             │    │
│  │  Scorecard: 78/100                                          │    │
│  │  ████████░░ Qualidade: 82                                   │    │
│  │  ███████░░░ Valuation: 75                                   │    │
│  │  ████████░░ Growth: 80                                      │    │
│  │  ██████░░░░ Leverage: 65                                    │    │
│  │  ███████░░░ Momentum: 72                                    │    │
│  │  █████████░ Dividend: 88                                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ FUNDAMENTAL ──────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  DRE (últimos 4 trimestres):                               │    │
│  │  Receita:  R$ 180B │ +15% YoY                             │    │
│  │  EBITDA:   R$ 65B  │ +22% YoY                             │    │
│  │  Lucro:    R$ 35B  │ +28% YoY                             │    │
│  │  Margem:   19.4%   │ +2.1pp                               │    │
│  │                                                             │    │
│  │  [echarts bar] Evolução trimestral                          │    │
│  │                                                             │    │
│  │  DCF Valuation:                                             │    │
│  │  Fair Value: R$ 44.20  │  Upside: +14.8%                  │    │
│  │  Cenário Bear: R$ 32.00 │  Base: R$ 44.20 │  Bull: R$ 58  │    │
│  │  [echarts] Cenários de valuation                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ TÉCNICO ─────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  [echarts candlestick] Gráfico de preços                    │    │
│  │  SMA20: R$37.80 │ SMA50: R$36.20 │ SMA200: R$34.50       │    │
│  │                                                             │    │
│  │  Indicadores:                                               │    │
│  │  RSI(14): 62.5    │  MACD: +0.45  │  Stoch: 58/42         │    │
│  │  ADX: 28.3        │  ATR: R$1.20  │  OBV: crescente       │    │
│  │                                                             │    │
│  │  Sinais:                                                    │    │
│  │  🟢 Tendência de alta (preço > SMA20 > SMA50)              │    │
│  │  🟢 Volume confirmando (acima da média)                     │    │
│  │  🟡 RSI neutro (nem sobrecomprado nem sobrevendido)         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ RISCO ────────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  Risco: MÉDIO (Score: 65/100)                              │    │
│  │                                                             │    │
│  │  Fatores:                                                   │    │
│  │  ⚠️ Exposição a commodities (oil price risk)               │    │
│  │  ⚠️ Risco político (governo intervention)                  │    │
│  │  ✅ Dívida controlada (Net Debt/EBITDA: 1.2x)              │    │
│  │  ✅ Caixa forte (R$ 45B disponível)                        │    │
│  │                                                             │    │
│  │  Stress:                                                    │    │
│  │  Oil -30%: -22% │ BRL -20%: +8% │ Selic +5%: -5%          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ VALUAÇÃO ─────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  Múltiplos vs Peers:                                        │    │
│  │  [echarts bar] P/E, EV/EBITDA, P/B comparativo             │    │
│  │                                                             │    │
│  │  DCF: R$ 44.20 (+14.8%) │ Reverse DCF implícito: 8% growth│    │
│  │  Relative: R$ 42.00 (+9.1%) │ Consenso: R$ 45.00 (+16.9%) │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## MODELOS DE DADOS NECESSÁRIOS

### Novas Tabelas

| Tabela | Campos Principais | Descrição |
|--------|-------------------|-----------|
| `portfolio_recommendations` | id, portfolio_id, type, ticker, confidence, rationale, target_weight, current_weight, stop_loss, target_price, status, created_at, decided_by, decided_at | Recomendações dos agents |
| `portfolio_trades` | id, portfolio_id, recommendation_id, ticker, side, quantity, price, order_type, status, executed_at, fees | Histórico de operações |
| `trade_journal` | id, trade_id, entry_signal, exit_signal, holding_days, return_pct, attribution, lessons | Diário de trades |
| `portfolio_alerts` | id, portfolio_id, alert_type, severity, message, triggered_at, acknowledged_at | Alertas automáticos |
| `portfolio_scorecards` | id, portfolio_id, as_of, overall_score, pillar_scores (JSONB), coverage | Scorecards periódicos |

### Tabelas Existentes que Precisam de Extensão

| Tabela | Campo a Adicionar | Tipo |
|--------|-------------------|------|
| `model_portfolios` | `objective`, `strategy_type`, `rebalance_frequency` | TEXT, TEXT, TEXT |
| `institutional_portfolio_versions` | `expected_return_12m`, `risk_score` | NUMERIC, INTEGER |

---

## AGENTS NECESSÁRIOS

### Novo Agent: `portfolio_advisor`

| Campo | Valor |
|-------|-------|
| Nome | Portfolio Advisor |
| Modelo | gpt-4o (temp=0.2) |
| Tools | `get_financial_metrics`, `search_evidence`, `calculate_valuation` |
| Input | portfolio_id, positions, risk_snapshot, performance_history |
| Output | Recommendations[], risk_assessment, performance_outlook |

### Agents Existentes a Conectar

| Agent | Conexão |
|-------|---------|
| `fundamentalist_analyst` | Análise de cada posição da carteira |
| `risk_director` | Avaliação de risco periódica |
| `investment_committee` | Aprovação de recomendações |
| `macro` | Análise macro para timing |
| `news` | Monitoramento de notícias |
| `political` | Risco político |

---

## WORKFLOWS TEMPORAIS

### 1. `PortfolioAnalysisWorkflow`

```
Trigger: Criação/atualização de carteira
Steps:
  1. Collect portfolio data (positions, risk, performance)
  2. For each position: run fundamentalist_analyst
  3. Run risk_director for portfolio-level risk
  4. Run macro for market context
  5. Run portfolio_advisor for recommendations
  6. Persist recommendations
  7. Notify gestor
```

### 2. `PortfolioMonitoringWorkflow` (Scheduled)

```
Trigger: Diário às 18:00 (após fechamento)
Steps:
  1. Fetch latest prices
  2. Recalculate NAV
  3. Check risk limits
  4. Check concentration limits
  5. Generate alerts if needed
  6. Update scorecards
```

### 3. `TradeExecutionWorkflow`

```
Trigger: Aprovação de recomendação
Steps:
  1. Validate compliance
  2. Calculate order size
  3. Send to broker (or simulate)
  4. Update position
  5. Calculate fees
  6. Publish NAV
  7. Register audit
```

---

## RESUMO DO ESCOPO

| Fase | Itens | Dias Est. |
|------|-------|-----------|
| 1. Criação de carteira | Formulário, listagem, API | 2 |
| 2. Detalhe da carteira | 8 tabs com dados reais | 4 |
| 3. Dashboard principal | KPIs, gráficos, alertas | 2 |
| 4. Agent portfolio_advisor | Novo agent + workflow | 3 |
| 5. Recomendações | Cards, aprovação, histórico | 2 |
| 6. Execução de ordens | Order flow, positions update | 2 |
| 7. Performance attribution | Métricas, decomposition | 2 |
| 8. Gráficos echarts | 10+ tipos de gráficos | 2 |
| **TOTAL** | | **19 dias** |
