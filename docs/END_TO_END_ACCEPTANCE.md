# Critérios de aceite ponta a ponta

## Cenário A — Cadastro manual bem-sucedido

1. Usuário com `candidates:create` informa `WEGE3`.
2. API exige `Idempotency-Key` e organização.
3. Candidato é criado em `identity_resolution`.
4. Lacunas padrão são criadas.
5. Outbox inicia `CandidateAnalysisWorkflow`.
6. Instrument master resolve listagem, instrumento e emissor.
7. Discovery encontra site, RI, relatórios, CVM e B3.
8. Validator confirma oficialidade e confiança mínima.
9. Documentos atuais são preservados e processados.
10. Dados passam por qualidade.
11. Pesquisa possui evidência suficiente.
12. Risco não encontra hard breach.
13. Comitê emite decisão.
14. Candidato fica `approved` e `approved_portfolio_eligible=true`.
15. Nenhuma posição é criada.

Aceite:

- cada etapa é auditável;
- reprocessamento não duplica objetos;
- todas as datas são timezone-aware;
- decisão referencia versões de dados, agents e evidências.

## Cenário B — RI não encontrado

1. Identity resolve.
2. CVM e B3 são encontradas.
3. RI e relatórios não são confirmados.
4. Candidato fica `awaiting_user_input`.
5. `final_decision` permanece nulo ou `pending`.
6. Interface mostra lacunas, motivo e ação requerida.
7. Nenhuma pesquisa final ou aprovação acontece.

Aceite:

- ausência não vira URL inventada;
- ausência não vira confiança baixa com continuação silenciosa;
- usuário consegue fornecer URL.

## Cenário C — Usuário complementa a página de relatórios

1. Usuário abre o candidato.
2. Envia URL com `If-Match` atual.
3. Fonte entra `discovered`, `official=false`.
4. `CandidateSourceValidationWorkflow` é iniciado.
5. Validador rejeita SSRF e confirma identidade.
6. Fonte passa a `verified`, `official=true`.
7. Gap correspondente é resolvido automaticamente.
8. Usuário solicita reanálise.
9. Nova execução usa número incremental e mantém histórico anterior.

Aceite:

- ETag antigo retorna 412;
- URL duplicada é idempotente;
- fonte inválida não resolve gap;
- versão anterior não é apagada.

## Cenário D — URL maliciosa

Testar:

- `localhost`;
- `127.0.0.1`;
- `::1`;
- faixa privada;
- link-local;
- endpoint de metadata;
- host público que redireciona para privado;
- DNS rebinding;
- resposta maior que o limite;
- cadeia de redirect excessiva;
- esquema não permitido;
- credenciais embutidas na URL.

Aceite:

- request é bloqueado antes do fetch sensível;
- evento de segurança é emitido;
- fonte recebe `rejected` ou permanece pendente;
- nenhum conteúdo é enviado ao agent.

## Cenário E — Exploração autônoma

1. Schedule cria uma execução única para a ocorrência.
2. Universe provider constrói universo em `data_as_of`.
3. Restricted/inativo/baixo volume/baixa cobertura são removidos.
4. Screener determinístico ranqueia.
5. Agent recebe shortlist limitada.
6. Agent tenta sugerir ticker fora da shortlist.
7. Sistema descarta esse ticker.
8. Sugestões válidas são persistidas com expiração.
9. Usuário promove uma sugestão.
10. Candidato é criado com origem `explorer`.
11. Investigação completa começa.

Aceite:

- retry da activity agendada não cria duas execuções;
- exploração não cria posição;
- promoção repetida retorna o mesmo candidato;
- sugestão expirada não pode ser promovida;
- motivo de dispensa é armazenado separadamente.

## Cenário F — Dados financeiros inconsistentes

1. Fontes e documentos são encontrados.
2. Reconciliação falha.
3. Dados ficam em quarentena.
4. Gap de qualidade bloqueante é criado.
5. Candidato fica `awaiting_user_input` ou `data_quality` bloqueado.
6. Agent não recebe fatos não promovidos como verdade.

## Cenário G — Pesquisa inconclusiva

1. Métricas existem.
2. Evidência de uma premissa crítica não existe.
3. Agent informa `data_gaps`.
4. Cobertura fica abaixo do limite.
5. Candidato recebe decisão `pending`.
6. Interface informa exatamente o que falta.

## Cenário H — Rejeição

Rejeição pode decorrer de:

- identidade incorreta;
- fonte fraudulenta;
- dados não confiáveis;
- tese fundamentalista negativa;
- risco rígido;
- comitê.

Aceite:

- motivo e estágio são registrados;
- rejeição não apaga pesquisa;
- reanálise só ocorre por comando e versão nova;
- rejeitado nunca é elegível para carteira.

## Cenário I — Integração com carteira

1. Candidato aprovado aparece no universo de candidatos elegíveis.
2. Mandato aplica filtros próprios.
3. Valuation e tese ativos são exigidos.
4. Otimizador gera proposta.
5. Risco valida.
6. Comitê aprova versão de carteira.
7. Paper execution processa a versão.

Aceite:

- candidato aprovado sozinho não insere posição;
- versão de carteira registra tese e valuation usados;
- ordem real permanece desabilitada no MVP.
