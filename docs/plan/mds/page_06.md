Manter.

Reduzir.

Sair.

Substituir por outra ação.

Aguardar dado adicional.

A recomendação deve incluir critérios de invalidação e prazo de revisão.

# **Contratos estruturados dos agentes**

Nunca grave apenas um texto como:

 “A empresa parece boa, mas existem alguns riscos.”

Use Structured Outputs com JSON Schema ou Pydantic. A documentação atual da OpenAI permite restringir a resposta a um schema e integrá-lo diretamente a modelos [Pydantic ou Zod. (OpenAI Developers)](https://developers.openai.com/api/docs/guides/structured-outputs?utm_source=chatgpt.com)

Exemplo simplificado:

```
 { "issuer_id": "uuid", "analysis_type": "filing_review", "data_as_of": "2026-07-16T18:00:00-03:00", "verdict": "positive", "confidence": 0.78, "thesis_effect": "strengthen", "materiality": 0.84, "time_horizon": "6_12_months", "claims": [ { "claim": "A margem operacional avançou em relação ao mesmo período.", "status": "verified", "source_document_id": "uuid", "source_location": "DFP, nota 24, página 71", "metric_ids": ["ebit_margin_yoy"] } ], "risks": [ { "type": "leverage", "severity": "medium", "description": "A cobertura de juros permanece pressionada." } ], "assumptions": [], "data_gaps": [], "invalidation_triggers": [ "net_debt_ebitda > 3.5", "two_consecutive_quarters_negative_fcf" ] }

```
A confiança não deve ser somente a confiança declarada pelo modelo. Ela deve ser posteriormente calibrada com um conjunto histórico de análises corretas e incorretas.

# **Modelo de dados**

As tabelas mais importantes seriam:

 **Cadastro e mercado**

 **Documentos**
