Data real da publicação.

Custos.

Slippage.

Impostos.

Limites de liquidez.

Delays entre sinal e execução.

Benchmarks.

Paper trading após o backtest.

 Feast documenta o conceito de point-in-time join, no qual somente features conhecidas até o timestamp do evento podem ser recuperadas. Mesmo que você não use [Feast no MVP, implemente esse comportamento no seu modelo de dados. (Feast)](https://docs.feast.dev/getting-started/concepts/feature-retrieval?utm_source=chatgpt.com)

 Para modelos temporais, não faça divisão aleatória de treino e teste. Use validação walk-forward ou divisões temporais; o `TimeSeriesSplit` do scikit-learn foi criado [justamente para evitar treinar no futuro e avaliar no passado. (Scikit-learn)](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html?utm_source=chatgpt.com)

 **Métricas do backtest**

CAGR.

Volatilidade.

Sharpe.

Sortino.

Calmar.

Máximo drawdown.

Tempo de recuperação.

Alpha após custos.

Beta.

Hit rate.

Profit factor.

Turnover.

Exposição média.

Concentração.

CVaR.

Capacidade.

Desempenho por regime de mercado.

Compare sempre com baselines simples:

Ibovespa.

Equal weight.

Buy and hold.

Ranking puramente quantitativo.

Carteira sem notícias.

Carteira sem LLM.

Assim você descobre se os agentes realmente adicionam valor.

# **Avaliação dos agentes**

Avalie o sistema em três níveis.

 **1. Extração**

Exatidão dos valores.

Unidade correta.

Período correto.

Entidade correta.

Localização da evidência.

Detecção de ausência de informação.

Tratamento de tabelas e notas.

 **2. Interpretação**

Classificação correta do evento.

Materialidade.

Distinção entre fato e opinião.
