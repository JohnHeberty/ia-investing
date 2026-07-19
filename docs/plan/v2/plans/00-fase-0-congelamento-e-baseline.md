# Fase 0 — Congelamento e baseline

[Índice](README.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Criar uma linha de base reproduzível antes das refatorações. Ao final, o time conhece o que existe, consegue executar os testes atuais de forma determinística e possui gates mínimos para impedir regressões silenciosas.

## Critérios de entrada

- Acesso administrativo ao repositório e ao provedor de CI.
- Branch principal e histórico atual identificados.
- Responsável técnico autorizado a criar tag, proteção de branch e políticas de merge.

## Estado atual e lacunas

O repositório possui backend Python, modelos SQLAlchemy, conectores, workflows, prompts e testes unitários, mas não registra baseline formal de build, cobertura, schemas, fontes, dependências ou riscos. A stack não está validada ponta a ponta. O PDF em `docs/books/` requer comprovação de licença ou remoção do histórico público.

## Escopo

- Tag imutável do estado anterior à transformação.
- Inventários de módulos, deployables, schemas, tabelas, prompts, workflows, fontes e dados licenciados.
- ADRs para monólito modular, Temporal, Raw Zone, point-in-time, migrations-only e separação entre fatos e agents.
- Fixtures mínimas e legalmente redistribuíveis de CVM e B3.
- CI de baseline, relatório de dependências e backlog P0/P1/P2.
- Convenções de nomes, contratos, temporalidade, erros e eventos de domínio.

Ficam fora de escopo correções funcionais, reorganização de pacotes e criação de migrations; pertencem à Fase 1.

## Workstreams

### Governança e inventário

Registrar commit/tag de baseline e gerar documentos versionados com: módulos e imports públicos, entrypoints, variáveis de ambiente, modelos/tabelas, schemas Pydantic, prompts existentes/ausentes, task queues, fontes/URLs/licenças e arquivos de dados. Classificar cada item como preservar, refatorar ou remover.

### Qualidade e CI

Fixar Python 3.12 e comandos canônicos (`uv sync`, Ruff, mypy, pytest). Registrar resultado, duração, falhas conhecidas e cobertura inicial sem reduzir gates para ocultar falhas. Adicionar scan de secrets e dependências em modo informativo; promover a obrigatório após triagem.

### Fixtures e conformidade

Selecionar amostras pequenas de diferentes setores e anos. Cada fixture deve ter origem, data de captura, hash, licença e transformação aplicada. Não copiar conteúdo sem autorização. Abrir decisão jurídica específica para o livro presente no repositório.

### Backlog e decisões

Converter P0-01 a P0-20 em itens rastreáveis, com fase de destino, dependências e critério de aceite. ADRs devem registrar contexto, decisão, alternativas e consequências, sem tentar antecipar detalhes ainda não validados.

## Sequência de pull requests

| PR | Conteúdo | Validação |
| --- | --- | --- |
| `F0-PR01` | Tag de baseline, inventário do repositório e mapa de deployables | Inventário referencia todos os diretórios de runtime |
| `F0-PR02` | Inventário de schemas, banco, workflows, prompts e fontes | Comparação automatizada ou checklist sem itens órfãos |
| `F0-PR03` | ADRs iniciais e convenções de domínio/temporalidade | Revisão arquitetural aprovada |
| `F0-PR04` | Fixtures CVM/B3 com metadados de origem e licença | Hashes estáveis e testes de leitura |
| `F0-PR05` | CI básico e relatório de baseline | Pipeline executa em clone limpo |
| `F0-PR06` | Backlog priorizado e parecer sobre conteúdo licenciado | Todos os P0 possuem destino e gate |

## Interfaces e artefatos

Esta fase não altera APIs. Define os formatos documentais mínimos para `source inventory`, `schema inventory`, ADR, registro de fixture e backlog. IDs usados nesses artefatos devem ser estáveis para serem citados pelas fases posteriores.

## Segurança, observabilidade e falhas

- Sanitizar saídas de CI e inventários para não registrar secrets.
- Executar secret scan antes de publicar relatórios.
- Se testes não iniciarem, registrar a falha como baseline; não corrigir no mesmo PR.
- Se uma fixture não puder ser redistribuída, armazenar somente receita de obtenção, hash e metadados.

## Testes e evidências

- Clone limpo instala dependências declaradas ou registra precisamente o bloqueador.
- Ruff, mypy e pytest produzem relatórios anexados ao baseline.
- Fixtures são lidas de forma offline e seus hashes são verificados.
- Links dos inventários apontam para símbolos ou caminhos existentes.
- A tag resolve exatamente para o commit auditado.

## Critérios de saída

- [ ] Branch principal protegida e CI requerido para merge.
- [ ] Tag e métricas de baseline publicadas.
- [ ] Inventários e ADRs revisados.
- [ ] Fixtures possuem proveniência e licença verificável.
- [ ] P0/P1/P2 possuem prioridade, dependência, fase e aceite.
- [ ] Questão de licenciamento possui decisão e ação registrada.
- [ ] Runbook de execução local e de CI disponível.

## Riscos e passagem para a Fase 1

O maior risco é transformar falhas conhecidas em exceções permanentes do CI. Toda exceção precisa de prazo ou condição de remoção e item de backlog. A Fase 1 recebe a tag, os relatórios, os ADRs, as fixtures e o mapa P0 como artefatos de entrada.
