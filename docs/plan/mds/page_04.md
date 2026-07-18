|/16/26, 5:27 PM|Col2|Recomendação principal|
|---|---|---|
|**Atividade**|**Agente de IA?**|**Implementação correta**|
|Classificar uma notícia por tipo de evento|Sim|Agente com saída estruturada|
|Avaliar impacto de uma notícia na tese|Sim|Agente com acesso às métricas|
|Calcular risco da carteira|Não|Motor quantitativo|
|Propor uma justificativa de rebalanceamento|Sim|Agente de comitê|
|Definir pesos finais|Híbrido|Otimizador + políticas + aprovação|
|Enviar ordem|Não diretamente|Serviço de execução protegido|

O LLM não deve ser sua calculadora financeira. Ele deve ser seu **analista de informações ambíguas** .

# **Agentes recomendados**

Não comece com quinze serviços separados. Comece com quatro agentes lógicos e divida apenas quando os contratos ficarem diferentes.

 **1. Coordenador de pesquisa**

Responsável por:

Receber o evento disparador.

Verificar quais dados já existem.

Chamar os especialistas necessários.

Consolidar resultados.

Encerrar cedo quando não houver informação material.

Encaminhar exceções para revisão.

Ele não deve decidir sozinho a compra ou venda.

 **2. Analista de documentos corporativos**

Entrada:

Documento original.

Período fiscal.

Métricas atuais e anteriores.

Última tese da empresa.

Saída:

Mudanças relevantes.

Guidance.

Riscos novos ou removidos.

Mudanças contábeis.

Alteração de estratégia.

Qualidade dos resultados.

Evidências com página, seção e documento.

Lacunas ou ambiguidades.

 **3. Analista de notícias e eventos**

Não faça somente análise de sentimento. Classifique o evento:

Resultado ou guidance.

Mudança de gestão.

M&A.

Regulação.

Processo judicial.

Fraude ou investigação.

Acidente operacional.

Alteração de rating.

Recompra, dividendos ou emissão.

Mudança competitiva.

Evento macroeconômico ou setorial.

A saída deve conter:
