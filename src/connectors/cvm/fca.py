"""CVM FCA — Formulário Cadastral de Companhia Aberta.

O ZIP anual do FCA carrega o registro estruturado da companhia: CNPJ, setor,
ticker, DRI, auditor, endereco etc. Onze CSVs em um unico ZIP."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from ..base import HttpClient

logger = logging.getLogger(__name__)


FCA_URL_TEMPLATE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{year}.zip"


class FCAGeneral(BaseModel):
    """Fatos principais da companhia (uma linha por CNPJ + versão)."""

    cnpj: str
    nome_empresarial: str
    cod_cvm: str
    dt_referencia: str
    versao: int = 0
    setor_atividade: str | None = None
    descricao_atividade: str | None = None
    pais_origem: str | None = None
    situacao_emissor: str | None = None
    situacao_registro_cvm: str | None = None
    categoria_registro_cvm: str | None = None
    especie_controle_acionario: str | None = None
    dia_encerramento_exercicio: int | None = None
    mes_encerramento_exercicio: int | None = None
    pagina_web: str | None = None


class FCASecurity(BaseModel):
    """Valor mobiliário emitido — ticker, classe, mercado, segmento."""

    cnpj: str
    nome_empresarial: str
    dt_referencia: str
    versao: int = 0
    valor_mobiliario: str
    classe_preferencial: str | None = None
    sigla_classe_preferencial: str | None = None
    codigo_negociacao: str | None = None
    mercado: str | None = None
    entidade_administradora: str | None = None
    segmento: str | None = None
    dt_inicio_negociacao: str | None = None
    dt_fim_negociacao: str | None = None


class FCAInvestorRelations(BaseModel):
    """Diretor de Relações com Investidores (DRI)."""

    cnpj: str
    nome_empresarial: str
    dt_referencia: str
    versao: int = 0
    responsavel: str | None = None
    email: str | None = None
    telefone: str | None = None


def _opt(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    s = v.strip()
    return s if s else None


def _int_opt(v: str | None) -> int | None:
    if v is None or not v.strip():
        return None
    try:
        return int(v.strip())
    except ValueError:
        return None


async def get_fca_geral(year: int, cnpj: str | None = None, client: HttpClient | None = None) -> list[FCAGeneral]:
    """Fatos principais da companhia: setor, situação, exercício social."""
    url = FCA_URL_TEMPLATE.format(year=year)
    from ._parser import fetch_csv_from_zip

    rows = await fetch_csv_from_zip(url, f"fca_cia_aberta_geral_{year}", client=client)

    if cnpj:
        target = cnpj.strip()
        rows = [r for r in rows if (r.get("CNPJ_Companhia") or "").strip() == target]

    return [
        FCAGeneral(
            cnpj=(r.get("CNPJ_Companhia") or "").strip(),
            nome_empresarial=_opt(r.get("Nome_Empresarial")) or "",
            cod_cvm=(r.get("Codigo_CVM") or "").strip(),
            dt_referencia=(r.get("Data_Referencia") or "").strip(),
            versao=_int_opt(r.get("Versao")) or 0,
            setor_atividade=_opt(r.get("Setor_Atividade")),
            descricao_atividade=_opt(r.get("Descricao_Atividade")),
            pais_origem=_opt(r.get("Pais_Origem")),
            situacao_emissor=_opt(r.get("Situacao_Emissor")),
            situacao_registro_cvm=_opt(r.get("Situacao_Registro_CVM")),
            categoria_registro_cvm=_opt(r.get("Categoria_Registro_CVM")),
            especie_controle_acionario=_opt(r.get("Especie_Controle_Acionario")),
            dia_encerramento_exercicio=_int_opt(r.get("Dia_Encerramento_Exercicio_Social")),
            mes_encerramento_exercicio=_int_opt(r.get("Mes_Encerramento_Exercicio_Social")),
            pagina_web=_opt(r.get("Pagina_Web")),
        )
        for r in rows
    ]


async def get_fca_valores_mobiliarios(
    year: int, cnpj: str | None = None, ticker: str | None = None,
    client: HttpClient | None = None,
) -> list[FCASecurity]:
    """Valores mobiliários emitidos — útil como mapa ticker → CNPJ."""
    url = FCA_URL_TEMPLATE.format(year=year)
    from ._parser import fetch_csv_from_zip

    rows = await fetch_csv_from_zip(url, f"fca_cia_aberta_valor_mobiliario_{year}", client=client)

    if cnpj:
        target = cnpj.strip()
        rows = [r for r in rows if (r.get("CNPJ_Companhia") or "").strip() == target]

    results = [
        FCASecurity(
            cnpj=(r.get("CNPJ_Companhia") or "").strip(),
            nome_empresarial=_opt(r.get("Nome_Empresarial")) or "",
            dt_referencia=(r.get("Data_Referencia") or "").strip(),
            versao=_int_opt(r.get("Versao")) or 0,
            valor_mobiliario=(r.get("Valor_Mobiliario") or "").strip(),
            classe_preferencial=_opt(r.get("Classe_Acao_Preferencial")),
            sigla_classe_preferencial=_opt(r.get("Sigla_Classe_Acao_Preferencial")),
            codigo_negociacao=_opt(r.get("Codigo_Negociacao")),
            mercado=_opt(r.get("Mercado")),
            entidade_administradora=_opt(r.get("Entidade_Administradora")),
            segmento=_opt(r.get("Segmento")),
            dt_inicio_negociacao=_opt(r.get("Data_Inicio_Negociacao")),
            dt_fim_negociacao=_opt(r.get("Data_Fim_Negociacao")),
        )
        for r in rows
    ]

    if ticker:
        target = ticker.strip().upper()
        results = [s for s in results if (s.codigo_negociacao or "").upper() == target]

    return results


async def get_fca_dri(
    year: int, cnpj: str | None = None, client: HttpClient | None = None,
) -> list[FCAInvestorRelations]:
    """Diretor de Relações com Investidores."""
    url = FCA_URL_TEMPLATE.format(year=year)
    from ._parser import fetch_csv_from_zip

    rows = await fetch_csv_from_zip(url, f"fca_cia_aberta_dri_{year}", client=client)

    if cnpj:
        target = cnpj.strip()
        rows = [r for r in rows if (r.get("CNPJ_Companhia") or "").strip() == target]

    return [
        FCAInvestorRelations(
            cnpj=(r.get("CNPJ_Companhia") or "").strip(),
            nome_empresarial=_opt(r.get("Nome_Empresarial")) or "",
            dt_referencia=(r.get("Data_Referencia") or "").strip(),
            versao=_int_opt(r.get("Versao")) or 0,
            responsavel=_opt(r.get("Responsavel")),
            email=_opt(r.get("Email")),
            telefone=_opt(r.get("Telefone")),
        )
        for r in rows
    ]
