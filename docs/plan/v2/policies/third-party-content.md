# Política de conteúdo e dados de terceiros

## Regra padrão

Somente versionar conteúdo de terceiro quando origem, licença, atribuição, finalidade, retenção e direito de redistribuição estiverem registrados. Na dúvida, falhar fechado: manter receita de captura e hash, não o conteúdo.

## Processo de entrada

1. Registrar proprietário, URL oficial, dataset/recurso, data de captura e contato quando aplicável.
2. Registrar licença/termos vigentes e restrições adicionais do metadado do conjunto.
3. Classificar como `redistributable`, `internal_only`, `metadata_only` ou `prohibited`.
4. Minimizar a amostra e remover dado pessoal/desnecessário.
5. Calcular SHA-256, tamanho, mídia, encoding e transformações.
6. Adicionar contract/integrity test e revisão de Data Governance.

## Mudança e remoção

- Mudança de licença pausa nova ingestão e abre incidente.
- Conteúdo expirado/proibido é removido do branch e artefatos; reescrita de histórico é uma operação separada, aprovada pelo owner e coordenada com consumidores.
- Outputs derivados mantêm lineage para permitir avaliação de impacto e exclusão.
- Fixtures sem redistribuição são recriadas em CI/ambiente autorizado ou substituídas por equivalentes sintéticos.

## Estado dos conteúdos atuais

| Conteúdo | Estado | Decisão operacional |
| --- | --- | --- |
| Fixtures CVM | `redistributable` com atribuição | ODbL e termos registrados em `tests/fixtures/manifest.json` |
| Fixture B3 | `synthetic` | Não contém observações copiadas; deriva apenas o contrato do layout oficial |
| `docs/books/O Rei dos Dividendos - Luiz Barsi Filho.pdf` | `blocked_pending_evidence` | Não redistribuir em novos artefatos/releases. Manter P0-20 aberto até comprovação escrita ou remoção coordenada do arquivo e histórico |
| PDFs dos planos internos | `project_owned_pending_owner_confirmation` | Confirmar autoria antes de distribuição externa |

Nenhum status desta tabela substitui parecer jurídico. O owner do repositório deve fornecer a evidência de autorização do livro; ausência de evidência resulta em remoção conforme o processo acima.
