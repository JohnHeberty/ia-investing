# Runbook de qualidade de dados e quarentena

## Visão geral

Incidentes de qualidade são criados automaticamente quando uma validação material falha no
`QualityGateService.apply_gate`. O incidente entra em status `open` e o registro de quarentena
(`QuarantineRecord`) fica `blocked`, impedindo a promoção canônica. Toda transição de status
requer a permissão `quality_incidents:manage`.

### Transições permitidas

```
open ──────► acknowledged ──────► resolved
 │                 │
 │                 └─────────────► waived
 │
 ├───────────────────────────────► resolved
 └───────────────────────────────► waived

waived ───► open   (somente se a waiver expirar)
```

### Status de quarentena

| Status      | Significado                                    |
|-------------|------------------------------------------------|
| `blocked`   | Dados retidos, não promovidos                   |
| `released`  | Incidente resolvido ou waivado — promoção liberada |
| `discarded` | Dados descartados definitivamente              |

## 1. Triagem de incidente

1. Liste incidentes em `open` ordenados por severidade (`critical` → `error` → `warning` → `info`).
2. Para cada incidente, avalie o `impact_summary` e o campo `evidence` (contém `entity_type`,
   `entity_id` e detalhes específicos da regra).
3. Determine a gravidade real:
   - **Crítica**: afeta preço, volume ou P&L — exige resposta em 4 h.
   - **Erro**: afeta dados auxiliares (setor, moeda) — exige resposta em 24 h.
   - **Aviso**: tolerância da regra excedida marginalmente — exige resposta em 72 h.
   - **Info**: informativo, sem bloqueio — agenda de sprint.
4. Atribua um owner pelo `owner_role` registrado no incidente (ex.: `data-engineering`,
   `portfolio-analyst`).
5. Registre a decisão de triagem no log de auditoria via transição para `acknowledged`.

## 2. Resolução

1. Identifique a causa raiz a partir de `evidence` e dos logs de ingestão.
2. Aplique a correção (reprocessamento, correção de schema, patch de dados fonte).
3. Transicione o incidente para `resolved` com `reason` obrigatório contendo notas de resolução.
4. O registro de quarentena associado é automaticamente alterado para `released`.
5. Verifique se a revalidação posterior aprova a versão do objeto de origem.

### Reprocessamento

1. Confirme que o dado corrigido está disponível no `payload_reference` da quarentena.
2. Execute o pipeline de reprocessamento com o mesmo `source_object_version_id`.
3. O `QualityGateService.apply_gate` reavalia automaticamente; se a validação passar, a
   promoção canônica é liberada.
4. Se a validação falhar novamente, um novo incidente é criado — volte ao passo 1 da triagem.

## 3. Waiver (isenção)

Use waiver quando a falha é um falso positivo ou quando uma exceção temporária é autorizada.

1. Transicione o incidente para `waived` fornecendo:
   - `reason`: justificativa detalhada (obrigatório).
   - `waiver_expires_at`: data/hora futura de expiração (obrigatório).
2. O waiver é registrado com `waiver_approved_by` = sujeito autenticado.
3. O registro de quarentena é liberado (`released`).
4. Quando a waiver expirar, o incidente retorna automaticamente para `open` e a quarentena
   volta a `blocked`.
5. Monitore waivers ativos e valide se a condição que justificou a isenção persiste antes da
   expiração.

### Correção de falso positivo

1. Confirme que a regra de qualidade está aplicando um limiar incorreto ou que a normalização
   dos dados fonte mudou.
2. Abra waiver com expiração alinhada ao próximo ciclo de atualização da regra.
3. Crie um item de backlog para ajustar a `QualityRule` (atualizar `tolerance` ou `code`).
4. Após correção da regra, expire a waiver e valide com reexecução da validação.

## 4. Resposta a drift de schema

1. Ao detectar coluna ausente, tipo incompatível ou renomeação no schema fonte:
   - Confirme se o `QualityRule` vigente cobre a versão do schema.
   - Verifique se `valid_from` / `valid_to` da regra engloba a data da última atualização.
2. Se a regra está desatualizada:
   - Crie uma nova versão da `QualityRule` com `version` incrementado e `valid_from` = agora.
   - Ative o `valid_to` na versão anterior.
   - Sincronize via `scripts/sync_agent_registry.py` se aplicável.
3. Reprocesse os objetos de origem afetados contra a nova versão da regra.
4. Incidentes abertos contra a versão antiga são resolvidos com nota: "regra atualizada, revalidado".

## 5. Indisponibilidade de fonte (source outage)

1. Quando a fonte fica indisponível, os dados em trânsito entram em quarentena automaticamente.
2. **Não execute demotion automática**: dados parciais ou antigos permanecem em `blocked` até
   que a fonte retorne.
3. Marque os registros como `stale` no campo `evidence` do incidente (chave `stale: true`).
4. Monitore a saúde da fonte via connectors de status.
5. Quando a fonte retornar:
   - Reexecute a ingestão para o período afetado.
   - O `apply_gate` reavalia e cria novos incidentes se necessário.
   - Incidentes antigos com `stale: true` podem ser waivados se os dados reingestos passarem.
6. Registre no incidente a duração do outage e os períodos de dados afetados.

## 6. Monitoramento

Monitore os seguintes indicadores em dashboard ou alertas:

| Métrica                        | Limite sugerido                | Ação                                      |
|--------------------------------|--------------------------------|-------------------------------------------|
| Taxa de parse (sucesso/total)  | < 95 % por fonte               | Investigar conectores da fonte            |
| Incidentes em `open`           | 0 críticos, < 5 erros          | Triagem prioritária                       |
| Tempo médio de resolução       | < 24 h para critical/error     | Escalar para lead de engenharia           |
| Waivers ativas                 | < 3                            | Revisar justificativas próximas da expiração |
| Registros `blocked` em excesso | > 10 por fonte                 | Verificar gargalo de reprocessamento      |

### Consultas úteis

```sql
-- Incidentes abertos por severidade
SELECT severity, COUNT(*)
FROM quality_incidents
WHERE status IN ('open', 'acknowledged')
GROUP BY severity
ORDER BY CASE severity
  WHEN 'critical' THEN 1 WHEN 'error' THEN 2
  WHEN 'warning' THEN 3 WHEN 'info' THEN 4 END;

-- Waivers próximas da expiração (próximas 48 h)
SELECT id, waiver_reason, waiver_expires_at
FROM quality_incidents
WHERE status = 'waived'
  AND waiver_expires_at BETWEEN NOW() AND NOW() + INTERVAL '48 hours';

-- Quarentenas bloqueadas por tempo excessivo
SELECT qr.id, qi.severity, qr.created_at
FROM quarantine_records qr
JOIN quality_incidents qi ON qi.id = qr.quality_incident_id
WHERE qr.status = 'blocked'
  AND qr.created_at < NOW() - INTERVAL '7 days'
ORDER BY qi.severity, qr.created_at;
```

## 7. Procedimento de emergência

Em caso de incidente crítico em massa (falha de regra atingindo múltiplas fontes):

1. Bloqueie novas promoções canônicas para as fontes afetadas.
2. Liste todos os incidentes `open`/`acknowledged` com `severity = 'critical'`.
3. Para cada incidente, avalie se o dado original está correto ou corrompido.
4. Se correto: waiver em lote com justificativa padronizada e expiração curta (24 h).
5. Se corrompido: resolva com reprocessamento e validação contra a versão corrigida.
6. Registre a decisão no log de auditoria com `correlation_id` único para o lote.
7. Após estabilização, execute a query de quarentenas bloqueadas > 7 dias para confirmar
   que nenhum registro ficou órfão.
