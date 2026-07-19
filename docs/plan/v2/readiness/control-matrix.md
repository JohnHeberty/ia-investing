# Control matrix — versão draft 1

| ID | Risco/obrigação | Controle | Tipo | Owner role | Frequência | Evidência e teste | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LEG-01 | uso fora do perímetro | banner paper, ausência de broker e gate fail-closed | preventivo | Legal/Compliance | por release | OpenAPI, dependency scan, parecer | parcialmente testado |
| DATA-01 | uso sem direito | Source Registry com licença/retenção e raw lineage | preventivo | Data Governance | por fonte/termo | registry, contrato, parecer | revisão externa pendente |
| DATA-02 | conhecimento futuro | `knowledge_at` e queries PIT | preventivo | Data | por pipeline | PIT/golden tests | testado |
| SEC-01 | acesso indevido | OIDC, RBAC/ABAC, tenant/team e service identity | preventivo | Security | contínuo | auth tests, pentest | pentest pendente |
| GOV-01 | autoaprovação | four-eyes em agent, carteira, paper e kill release | preventivo | Risk | por decisão | audit logs e testes | testado |
| OPS-01 | execução indevida | `environment=paper` no banco e sem send-order | preventivo | Operations | por release | constraints/security test | testado |
| OPS-02 | divergência contábil | reconciliação order/fill/ledger e bloqueio crítico | detectivo | Operations | diária | breaks, alerts, drill | drill pendente |
| OPS-03 | incidente | kill switch global/carteira com liberação four-eyes | corretivo | Operations | semestral | audit log e drill | drill pendente |
| MODEL-01 | modelo não governado | versões, evals, budgets, tracing e promotion humana | preventivo | Model Risk | por versão | registry/evals/validation | validação independente pendente |
| READY-01 | decisão incompleta | pack imutável, quórum, expiração e findings | preventivo | Readiness Committee | por gate | hash, votos, decisão | mecanismo testado |

Antes do decision pack, cada linha deve apontar para UUIDs de `readiness_evidence`, findings/remediações e retestes. Exceção exige validade; finding crítico aberto nunca pode ser aceito.
