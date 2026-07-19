# Threat model — rascunho interno

## Ativos e trust boundaries

Ativos: raw documents, dados licenciados, evidence/claims, prompts, decisões, portfolios, ledger paper, identities, secrets e audit trail. Boundaries: browser→Next.js, Next.js/API→FastAPI, API/workers→Postgres/MinIO/Temporal, workers→fontes allowlisted e provider de IA. Conteúdo externo é input não confiável.

## Ameaças prioritárias

- Tenant escape, privilege escalation e violação de four-eyes.
- Prompt injection que solicita secret, filesystem, SQL, internet ou ação de trading.
- SSRF/egress não autorizado e exfiltração por logs/traces.
- Poisoning, schema drift, duplicação e knowledge leakage.
- Replay/concorrência criando ordem ou fill duplicado.
- Alteração destrutiva de raw, evidence, forecast, fill ou ledger.
- Supply-chain compromise em Python, npm e imagens.

## Controles a auditar

OIDC/MFA, tenant/team authorization, typed tools, allowlists, idempotency/unique constraints, append-only records, redaction, TLS/at-rest encryption, secret rotation, dependency/secret/SAST/container scans, restricted list, backup/restore e audit immutability. Pentest e reteste independentes continuam obrigatórios; este documento não os substitui.
