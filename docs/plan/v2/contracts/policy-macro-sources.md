# Contratos de fontes políticas e macro

| Código | Contrato | Frequência | Rate limit conservador | Autenticação | Redistribuição |
| --- | --- | ---: | ---: | --- | --- |
| `camara-dados-abertos` | REST API v2/JSON | 60 min | 60/min | pública | revisão jurídica pendente |
| `senado-dados-abertos` | Swagger atual/JSON | 60 min | 30/min | pública | revisão jurídica pendente |
| `dou-inlabs` | XML INLABS | diária | 20/min | secret reference | revisão jurídica pendente |
| `bcb-sgs` | SGS/JSON | diária | 30/min | pública | revisão jurídica pendente |
| `ibge-sidra` | SIDRA/JSON | diária | 30/min | pública | revisão jurídica pendente |

Os limites são internos e deliberadamente conservadores, não uma declaração de quota do provedor. Egress aceita apenas hosts oficiais registrados. Payload é preservado na Raw Zone antes do parsing, com SHA-256, timestamps e versão do parser. Fixtures políticas são sintéticas e validam somente o contrato; não concedem direito de redistribuir conteúdo oficial.

Schema drift pausa a fonte, marca freshness como stale e segue o runbook `policy-intelligence.md`. A licença `official-public-access-legal-review-required` mantém `permits_redistribution=false` e `reviewed_at=null` até parecer formal; portanto o gate jurídico continua aberto.
