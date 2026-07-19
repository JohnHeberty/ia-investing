# Runbook — Carteiras, NAV, risco e backtest

## Escopo e segurança

Este runbook cobre somente carteiras-modelo e execução `paper`. Não há integração com corretora. Registre organização, carteira, versão, `as_of`, correlation ID e operador em toda intervenção. Nunca edite snapshots, NAV, fills ou resultados de backtest; publique nova revisão ou lançamento compensatório.

## NAV ausente ou não reconciliado

1. Suspenda publicação e ranking da carteira.
2. Confirme versão aprovada, calendário, listing temporal, preços PIT, caixa e ledger.
3. Identifique posição sem preço, corporate action, fee/tax ou lançamento duplicado.
4. Corrija a fonte ou crie lançamento compensatório auditado.
5. Republique uma nova revisão do mesmo `as_of` e compare o hash dos inputs.

## Breach e waiver

1. Hard breach bloqueia proposta e operação paper; não altere a policy para liberar o fluxo.
2. Valide freshness, snapshot e versão da risk policy.
3. Quando permitido, waiver exige autoridade `risk:waive`, justificativa e expiração futura.
4. Expiração reabre o bloqueio. Para suspender, transicione a carteira com razão auditável e `If-Match` atual.

## Solver

1. Em `infeasible`/`failed`, preserve diagnóstico, slacks, solver/version e input hash; não use equal weight como sucesso.
2. Verifique universo mínimo, restricted list, cash, concentração e constraints conflitantes.
3. Só repita após novo input/config ou falha transitória comprovada. Timeout deve cancelar o workflow chamador.

## Backtest

1. Fixe config, seed, code version e data snapshot.
2. Confirme delay de sinal, benchmark fora do universo, calendário, custos, impostos e corporate actions conhecidos no cutoff.
3. Compare `config_sha256`, `data_sha256` e `result_sha256` no replay.
4. Divergência ou efeito de dado futuro no passado bloqueia promoção e abre incidente.

## Recuperação

Mantenha a carteira suspensa até NAV reconciliado, breaches resolvidos e replay estável. Anexe evidências e hashes ao incidente; retome somente com aprovação segregada.
