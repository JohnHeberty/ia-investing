# Runbook de pesquisa, revisão e evidência

## Triagem e revisão

1. Consulte o caso e confirme `data_as_of`, perguntas obrigatórias e assignments.
2. Verifique claims materiais no cutoff; evidência futura, revogada ou expirada não é suporte válido.
3. Crie o assessment com schema/version, validade e resultado estruturado.
4. Solicite revisão para o papel independente aplicável. O autor não pode decidir o próprio assessment.
5. Registre decisão, comentário e razão. `changes_requested` cria nova revisão; não sobrescreva o snapshot anterior.
6. Ative uma versão de tese somente após review aprovado, ao menos uma evidence e um claim verificado.

## Expiração e stale

Assessment vencido deve ter a revisão recusada como expirada. Tese ativa vencida é marcada `stale`; nunca prorrogue `expires_at` na versão existente. Abra novo draft, atualize fontes e valuation, preserve o diff e solicite nova aprovação. Enquanto stale, bloqueie consumo por construção de carteira.

## Conflito de edição

Commands de caso e tese usam `ETag`/`If-Match`. Em `412`, recarregue a versão atual, compare o diff e reaplique apenas mudanças intencionais. Não repita com ETag inventado nem altere diretamente o banco. Decisão de review duplicada retorna conflito e deve ser tratada como estado terminal.

## Correção ou revogação de evidência

Raw e evidence são append-only. Corrija a fonte criando nova versão e registre a linhagem; marque a evidence comprometida como revogada. Identifique claims, teses e valuations dependentes, reabra os casos materiais e gere versões substitutas. Preserve a evidência antiga para auditoria e nunca edite trecho/hash retroativamente.

## Diagnóstico e evidências operacionais

- Use `X-Correlation-ID`, audit logs e outbox para reconstruir autoria e transições.
- Compare `input_sha256`, `result_sha256` e `code_version` ao investigar valuation.
- Execute `python scripts/verify_valuation_replay.py` no ambiente com PostgreSQL para provar persistência e replay.
- Escale violação de licença, segregação de função ou dado crítico em quarentena; não use waiver implícito.
