# Perímetro do produto — rascunho para revisão jurídica

## Finalidade e público

O IA Investing OS v2 é uma plataforma interna de pesquisa, construção de carteiras-modelo e operação simulada. Usuários são equipes internas de Pesquisa, Gestão, Risco, Comitê, Operações, Dados e Auditoria. A jurisdição inicial é Brasil. Outputs apoiam análise interna; não são oferta pública, recomendação individualizada, consultoria a cliente, administração de recursos de terceiros ou ordem de negociação.

## Classificação de capacidades

| Capacidade | Classificação interna | Limite obrigatório |
| --- | --- | --- |
| Ingestão, pesquisa, tese e valuation | pesquisa interna | fonte, licença, cutoff, evidência e revisão |
| Otimização e backtest | simulação analítica | PIT, mandato e sem fallback silencioso |
| Carteira-modelo e comitê | decisão interna versionada | four-eyes, risco e audit trail |
| Orders/fills/NAV paper | simulação operacional | `environment=paper`, sem broker/credencial live |
| Readiness gate | governança | `go` autoriza somente novo plano |

## Fora de escopo

Clientes externos, suitability, aconselhamento individualizado, custódia, OMS/EMS, FIX, API de corretora, credenciais de trading e envio/cancelamento de ordem real. Qualquer expansão exige parecer jurídico formal, decisão de prontidão válida e novo plano aprovado.

## Bloqueadores externos

Especialista deve mapear CVM 19/20/21 e demais normas aplicáveis, responsabilidades profissionais, disclosures, conflitos, retenção e eventual suitability. Conclusão ausente ou inconclusiva permanece `no_go`.
