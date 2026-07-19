[A CVM oferece dados abertos e funcionalidades de download de documentos periódicos e eventuais, incluindo ITR, DFP, FRE, FCA e IPE. (Serviços e Informações do](https://www.gov.br/cvm/pt-br/assuntos/regulados/consultas-por-participante/companhias?utm_source=chatgpt.com) [Brasil)](https://www.gov.br/cvm/pt-br/assuntos/regulados/consultas-por-participante/companhias?utm_source=chatgpt.com)

 **B3**

Use a B3 para:

Cotações históricas.

Cadastro de instrumentos.

Informações de negociação e liquidez.

Fatos relevantes.

Plantão de notícias de empresas.

Índices e composição de índices.

Dados de mercado licenciados, caso precise de baixa latência.

 A B3 publica séries históricas e seus layouts, além de consultas de fatos relevantes e plantão de notícias. O portal B3 for Developers informa que suas APIs são destinadas
 [a clientes B2B e que não oferece acesso direto às APIs para pessoas físicas; portanto, valide contratação e licenciamento antes de basear o produto nelas. (B3)](https://b3.com.br/data/files/C8/F3/08/B4/297BE410F816C9E492D828A8/SeriesHistoricas_Layout.pdf?utm_source=chatgpt.com)

 **Relações com investidores**

Os sites de RI das empresas devem ser usados para:

Releases de resultados.

Apresentações.

Transcrições de conferências.

Planilhas operacionais.

Guidance.

Calendário de eventos.

Políticas corporativas.

Sempre prefira API, RSS, sitemap ou download direto. Playwright e automação de navegador devem ser último recurso.

 **Macroeconomia**

Use o Banco Central para Selic, câmbio, crédito, inflação esperada e séries financeiras; e o IBGE/SIDRA para inflação, atividade econômica, desemprego, indústria, serviços [e dados setoriais. Ambos disponibilizam serviços e APIs oficiais. (Banco Central do Brasil)](https://www.bcb.gov.br/api/?utm_source=chatgpt.com)

 **Notícias secundárias**

Crie uma hierarquia de confiança:

1. CVM, B3 e RI da empresa.

2. Órgãos reguladores, tribunais e agências governamentais.

3. Provedores financeiros licenciados.

4. Grandes veículos jornalísticos.

5. Agregadores.

6. Redes sociais e fontes não verificadas.

 GDELT pode ser útil para descoberta ampla e monitoramento global, mas não deve ser tratado como confirmação única de um evento. Para produção, verifique direitos
 de armazenamento, redistribuição e uso de texto integral. Por exemplo, o plano Developer do NewsAPI é explicitamente limitado a desenvolvimento e testes, não a [produção. (GDELT Project)](https://www.gdeltproject.org/?utm_source=chatgpt.com)

 **Estados Unidos, posteriormente**

 Para ações americanas, use as APIs públicas do SEC EDGAR para submissões e fatos XBRL. A SEC disponibiliza dados em JSON, mas estabelece uma política de acesso
 [justo com limite atual de até 10 requisições por segundo por usuário e exige identificação adequada das automações. (Comissão de Valores Mobiliários)](https://www.sec.gov/search-filings/edgar-application-programming-interfaces?utm_source=chatgpt.com)

# **Não transforme todas as etapas em agentes**

|Esta é uma das decisões mais importantes.|Col2|Col3|
|---|---|---|
|**Atividade**|**Agente de IA?**|**Implementação correta**|
|Baixar um CSV|Não|Conector HTTP determinístico|
|Verificar se um documento mudou|Não|Hash, ETag e metadados|
|Extrair dados estruturados de CSV/XBRL|Não|Parser e schema|
|Calcular ROIC, margem e endividamento|Não|Código testado|
|Conferir Ativo = Passivo + PL|Não|Regra de validação|
|Identificar mudança no discurso da administração|Sim|Agente de documentos|
