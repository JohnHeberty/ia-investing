# Runbook — Inteligência política e macro

## Schema drift ou parse failure

1. Pause somente o schedule da fonte afetada; preserve Raw Zone e hashes.
2. Marque a fonte como stale e impeça que freshness seja inferida como normal.
3. Reproduza com a fixture versionada e compare payload, parser e contrato.
4. Publique nova versão do parser; nunca altere versões jurídicas históricas.
5. Reprocesse idempotentemente e confirme identidade, `knowledge_at`, diff e duplicatas antes de retomar.

## Source outage

Não reduza probabilidade nem fabrique ausência de evento. Exiba a última observação como stale, registre incidente e mantenha alertas materiais pendentes. Retome com discovery a partir do último cursor confirmado.

## Correção e falso alerta

Correção humana cria nova assessment/version com ator, motivo, evidência e correlação. Não reescreva forecast resolvido. Para falso alerta, reconheça o alerta, registre causa (`mapping`, freshness, corroboration ou materiality) e ajuste uma regra versionada. Impacto material continua exigindo o `PolicyEventWorkflow`; decisão aprovada nunca altera tese automaticamente.

## Verificação

Execute `pytest -q tests/unit/test_policy_intelligence.py` e `python scripts/verify_policy_paper_workflows.py`. Confirme migrations no head com `alembic check` antes de reativar a fonte.
