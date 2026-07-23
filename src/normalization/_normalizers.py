"""Normalize raw CVM financial entries into canonical line-item dictionaries."""

from __future__ import annotations

from connectors.cvm._financials import FinancialEntry, _parse_valor

from ._mappings import _DESCRIPTION_PATTERNS, CVM_ACCOUNT_MAP


def _resolve_canonical(entry: FinancialEntry) -> str | None:
    cod = entry.cod_conta.strip()
    if cod in CVM_ACCOUNT_MAP:
        return CVM_ACCOUNT_MAP[cod]

    desc_lower = entry.desc_conta.strip().lower()
    for canonical, patterns in _DESCRIPTION_PATTERNS.items():
        for pattern in patterns:
            if pattern in desc_lower:
                return canonical

    return None


def normalize_bpa(rows: list[dict[str, object]]) -> dict[str, float]:
    entries = _to_entries(rows)
    result: dict[str, float] = {}

    current_assets = 0.0
    non_current_assets = 0.0

    asset_current = {
        "caixa",
        "aplicacoes_financeiras",
        "contas_receber",
        "estoques",
        "ativos_biologicos",
        "tributos_a_receber",
        "adiantamentos",
        "ativos_nao_correntes_manutencao",
    }

    for entry in entries:
        canonical = _resolve_canonical(entry)
        if canonical is None:
            continue
        result[canonical] = result.get(canonical, 0.0) + entry.valor
        if canonical in asset_current:
            current_assets += entry.valor
        else:
            non_current_assets += entry.valor

    result["ativo_circulante"] = current_assets
    result["ativo_nao_circulante"] = non_current_assets
    result["total_ativos"] = current_assets + non_current_assets

    return result


def normalize_bpp(rows: list[dict[str, object]]) -> dict[str, float]:
    entries = _to_entries(rows)
    result: dict[str, float] = {}

    current_liabilities = 0.0
    non_current_liabilities = 0.0
    equity = 0.0

    liab_current = {
        "fornecedores",
        "emprestimos_circulantes",
        "divida_bancaria_circulante",
        "obrigacoes_fiscais",
        "obrigacoes_trabalhistas",
        "dividendos_a_pagar",
        "adiantamentos_clientes",
        "outros_passivos_circulantes",
    }

    liab_non_current = {
        "emprestimos_nao_circulantes",
        "divida_bancaria_nao_circulante",
        "debentures",
        "obrigacoes_afetadas",
        "provisoes",
        "passivos_ambientais",
        "outros_passivos_nao_circulantes",
    }

    equity_accounts = {
        "capital_social",
        "reservas",
        "lucros_acumulados",
        "resultados_nao_apropriados",
        "ajustes_avaliacao",
        "outros",
    }

    for entry in entries:
        canonical = _resolve_canonical(entry)
        if canonical is None:
            continue
        result[canonical] = result.get(canonical, 0.0) + entry.valor
        if canonical in liab_current:
            current_liabilities += entry.valor
        elif canonical in liab_non_current:
            non_current_liabilities += entry.valor
        elif canonical in equity_accounts:
            equity += entry.valor

    result["passivo_circulante"] = current_liabilities
    result["passivo_nao_circulante"] = non_current_liabilities
    result["total_passivo"] = current_liabilities + non_current_liabilities
    result["patrimonio_liquido"] = equity

    return result


def normalize_dre(rows: list[dict[str, object]]) -> dict[str, float]:
    entries = _to_entries(rows)
    result: dict[str, float] = {}

    for entry in entries:
        canonical = _resolve_canonical(entry)
        if canonical is None:
            continue
        result[canonical] = result.get(canonical, 0.0) + entry.valor

    return result


def normalize_dfc(rows: list[dict[str, object]]) -> dict[str, float]:
    entries = _to_entries(rows)
    result: dict[str, float] = {}

    for entry in entries:
        canonical = _resolve_canonical(entry)
        if canonical is None:
            continue
        result[canonical] = result.get(canonical, 0.0) + entry.valor

    return result


def normalize_dmpl(rows: list[dict[str, object]]) -> dict[str, float]:
    return normalize_dfc(rows)


def normalize_dva(rows: list[dict[str, object]]) -> dict[str, float]:
    return normalize_dfc(rows)


def _to_entries(rows: list[dict[str, object]]) -> list[FinancialEntry]:
    entries: list[FinancialEntry] = []
    for r in rows:
        if isinstance(r, FinancialEntry):
            entries.append(r)
        elif isinstance(r, dict):
            raw_value = r.get("valor", r.get("VL_CONTA"))
            if raw_value is None or not str(raw_value).strip():
                raise ValueError("financial row has no value; represent absence with value_status")
            entries.append(
                FinancialEntry(
                    cnpj=str(r.get("cnpj", r.get("CNPJ_CIA", ""))),
                    nome_empresa=str(r.get("nome_empresa", r.get("DENOM_CIA", ""))),
                    cod_cvm=str(r.get("cod_cvm", r.get("CD_CVM", ""))),
                    dt_referencia=str(r.get("dt_referencia", r.get("DT_REFER", ""))),
                    versao=int(str(r.get("versao", r.get("VERSAO", 0)) or 0)),
                    cod_conta=str(r.get("cod_conta", r.get("CD_CONTA", ""))),
                    desc_conta=str(r.get("desc_conta", r.get("DS_CONTA", ""))),
                    valor=_parse_valor(str(raw_value)),
                    moeda=str(r.get("moeda", r.get("MOEDA", "REAL"))),
                    escala=str(r.get("escala", r.get("ESCALA_MOEDA", "MIL"))),
                    dt_inicio_exercicio=str(r.get("dt_inicio_exercicio", r.get("DT_INI_EXERC", ""))),
                    ordem_exercicio=str(r.get("ordem_exercicio", r.get("ORDEM_EXERC", ""))),
                    grupo_demonstracao=str(r.get("grupo_demonstracao", r.get("GRUPO_DFP", ""))),
                    coluna_demonstracao=str(r.get("coluna_demonstracao", r.get("COLUNA_DF", ""))),
                )
            )
    return entries
