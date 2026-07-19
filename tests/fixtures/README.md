# Fixtures de contrato

As fixtures deste diretório são amostras pequenas para testes offline. Elas não substituem os arquivos integrais nem devem ser usadas para análise financeira. Integridade, origem, licença e transformações ficam registradas em `manifest.json`.

## CVM

As amostras CAD, DFP e ITR foram reduzidas a registros necessários aos testes. A amostra `dfp_utility_consolidated_sample.csv` preserva linhas selecionadas dos arquivos consolidados BPA, BPP e DRE da DFP 2024 da ENGIE Brasil Energia. A amostra `dfp_financial_individual_restatement_sample.csv` preserva a versão 3 publicada para o BRB, cobrindo escopo individual e formulário reapresentado. Ambas foram convertidas de Windows-1252 para UTF-8 e reunidas sob um cabeçalho comum. Os valores continuam na escala `MIL` informada pela fonte.

Fonte: Portal de Dados Abertos CVM. Os datasets são publicados sob Open Data Commons ODbL; uso secundário deve citar a CVM e verificar os metadados atuais do conjunto.

Para recapturar a amostra utility:

1. Baixe `dfp_cia_aberta_2024.zip` da URL registrada no manifesto.
2. Leia os arquivos `BPA_con`, `BPP_con` e `DRE_con` em Windows-1252.
3. Filtre `CNPJ_CIA=02.474.103/0001-19`, `ORDEM_EXERC=ÚLTIMO` e as contas registradas nesta fixture.
4. Normalize o cabeçalho para o superset atual, deixe `DT_INI_EXERC` vazio em balanços e grave UTF-8.
5. Atualize o SHA-256 no manifesto somente após revisão do diff.

## B3

`cotahist_synthetic_sample.csv` é sintética: usa instrumentos conhecidos e valores ilustrativos para testar parsing, sem copiar observações de mercado. Seus campos seguem o layout oficial COTAHIST publicado pela B3. Alterações do layout oficial exigem contract test e nova versão da fixture.

## Política

- Não versionar arquivos integrais, conteúdo pago, credenciais ou dados pessoais desnecessários.
- Preferir amostras mínimas derivadas de fontes abertas ou dados inteiramente sintéticos.
- Registrar URL, captura, licença, encoding, transformação e hash antes do merge.
- Mudança de bytes exige atualização intencional do hash e revisão da proveniência.
- Se a licença não permitir redistribuição, versionar apenas gerador/receita e hash do artefato externo.
