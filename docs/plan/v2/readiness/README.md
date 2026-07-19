# Prontidão para decisão go/no-go

Estes documentos são artefatos internos de preparação da Fase 9. Não equivalem a parecer jurídico, pentest, auditoria independente, validação de model risk ou aprovação para execução real.

- `product-perimeter.md`: finalidade e capacidades autorizadas.
- `control-matrix.md`: controles, responsáveis por papel, frequência e evidência esperada.
- `threat-model.md`: ativos, trust boundaries, ameaças e controles a validar.
- `bcp-dr.md`: procedimento de backup, restore, DR e medição de RTO/RPO.

Evidências externas devem ser registradas pela API `/api/v1/readiness/evidence`, verificadas por pessoa autorizada e incluídas por UUID em um decision pack congelado. Ausência, expiração, finding crítico ou voto obrigatório ausente produz `no_go` automaticamente. Mesmo `go` autoriza apenas planejar um projeto futuro; nunca execução live.
