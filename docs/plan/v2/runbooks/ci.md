# Runbook de CI

## Checks

O workflow `.github/workflows/ci.yml` possui jobs de qualidade/testes e segurança. Ruff lint, compileall e pytest são bloqueantes. Format, mypy, dependency audit e secret scan começam informativos por causa dos débitos documentados; devem virar obrigatórios assim que seus itens P1 forem encerrados.

## Triagem

1. Abra o job e baixe o artifact correspondente ao SHA.
2. Confirme se a falha reproduz com `.python-version` e a versão de `uv` do workflow.
3. Execute localmente o mesmo comando via `uv run`.
4. Classifique como regressão, dependência/fonte instável ou flaky test.
5. Corrija a causa; não use `continue-on-error`, skip ou redução de cobertura sem item, justificativa e expiração.

## Relatórios

- Quality: Ruff, mypy, JUnit e coverage XML/texto.
- Security: pip-audit e detect-secrets em JSON.
- Retenção inicial: 30 dias.

## Proteção da branch

No GitHub, exigir pull request e o job `Quality and tests` antes de merge em `main`. Impedir force push/deletion e exigir resolução de conversas. O job de segurança deve ser promovido a obrigatório após a primeira triagem. Essa configuração é externa ao repositório e só pode ser marcada como concluída após captura ou consulta da regra ativa.

## Incidente

Se secret real aparecer no histórico, revogue-o antes de limpar o Git. Suspenda deploy/ingestão afetados, registre incidente e coordene qualquer reescrita de histórico. Dependency finding crítico bloqueia release até correção ou waiver formal com expiração.
