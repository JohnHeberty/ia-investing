# Runbook do runtime de agents

## Sincronização e startup

O manifesto canônico é `prompts/registry.json`. A API valida existência, path e SHA-256 de
todos os prompts e schemas no startup; divergência impede a inicialização. Após aplicar as
migrations, sincronize os artefatos de forma idempotente:

```bash
python scripts/sync_agent_registry.py --actor deployment:<release-id>
```

A primeira versão de cada capability é bootstrap auditado. Mudanças posteriores criam uma
versão `candidate`; nunca altere artefatos já persistidos.

## Provider indisponível

Confirme `error_code`, `run_id`, capability, versão e trace, sem copiar prompt ou input para
logs. Erros `provider_transient` podem repetir com o mesmo run, versão e input. Erros
`provider_rejected` e outputs inválidos exigem correção do candidato. O provider mock é apenas
fixture explícita de teste e nunca é fallback silencioso de produção.

## Budget ou guardrail

Runs com `budget_exceeded`, `prompt_injection`, `unknown_citation`, `citation_coverage` ou
`cutoff_mismatch` falham fechados. Não reative a tese nem execute command. Preserve hashes,
evidence IDs e trace; remova dados pessoais do incidente. Ajustes de budget, prompt ou schema
geram nova versão e passam por eval.

## Aprovação humana

Tools sensíveis criam `CommandReceipt` e `agent_approval_requests`. O aprovador precisa da
permissão `agent_approvals:decide`, não pode ser o solicitante e deve registrar razão. Aprovação
expirada não retoma o run. A retomada usa `agent_version_id`, input e cutoff já fixados.

## Rollback e incidente

Promova novamente a versão anterior somente com eval aprovado ou override autorizado com
justificativa e expiração. A operação atualiza o ponteiro ativo e mantém runs históricos.
Durante um incidente, bloqueie novas submissões da capability, deixe runs em voo terminar ou
cancele-os explicitamente, registre a decisão no log de auditoria e valide um run mockado antes
de reabrir o tráfego.
