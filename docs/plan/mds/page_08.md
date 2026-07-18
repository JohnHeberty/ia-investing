Isso é indispensável para impedir que um backtest utilize uma informação que ainda não estava disponível naquele momento.

# **Raw Zone e rastreabilidade**

Todo arquivo baixado deve ser preservado antes da transformação.

Metadados mínimos:

``` source_url retrieved_at published_at content_type sha256 http_etag http_last_modified issuer_id document_type reporting_period parser_version license_policy

``` O fluxo deve ser:

1. Descobrir.

2. Baixar.

3. Calcular hash.

4. Verificar duplicidade.

5. Guardar o original.

6. Publicar o evento `document.downloaded` .

7. Interpretar o documento.

8. Validar.

9. Só então atualizar os dados canônicos.

Em caso de erro futuro no parser, você conseguirá reprocessar todo o histórico sem baixar novamente.

# **Métricas recomendadas**

 **Qualidade e crescimento**

Receita YoY e CAGR.

Crescimento orgânico versus aquisição.

Margem bruta, EBITDA, EBIT e líquida.

ROIC.

ROE.

Giro de ativos.

Conversão de EBITDA em caixa.

Fluxo de caixa livre.

FCF margin.

Qualidade do lucro e accruals.

Diluição acionária.

Recorrência e previsibilidade de receita.

 **Endividamento**

Dívida líquida/EBITDA.

Cobertura de juros.

Dívida/fluxo de caixa.

Perfil de vencimentos.
