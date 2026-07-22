from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Portfolio:
    id: str
    name: str
    sector: str
    nav: Decimal
    volatility: Decimal
    var_95: Decimal
    sharpe: Decimal
    max_drawdown: Decimal
    last_rebalanced: date
    status: str


@dataclass(frozen=True)
class Holding:
    ticker: str
    name: str
    sector: str
    weight: Decimal
    market_value: Decimal
    accumulated_return: Decimal
    days_held: int


@dataclass(frozen=True)
class Thesis:
    id: str
    title: str
    status: str
    conviction_score: Decimal
    expected_return: Decimal
    timeframe: str


PORTFOLIOS = {
    "pf-finance": Portfolio(
        id="pf-finance",
        name="Fundo Ações Financeiras",
        sector="finance",
        nav=Decimal("1_250_000_000"),
        volatility=Decimal("0.152"),
        var_95=Decimal("0.021"),
        sharpe=Decimal("1.24"),
        max_drawdown=Decimal("-0.118"),
        last_rebalanced=date(2026, 6, 15),
        status="active",
    ),
    "pf-energy": Portfolio(
        id="pf-energy",
        name="Fundo Energia Sustentável",
        sector="energy",
        nav=Decimal("875_000_000"),
        volatility=Decimal("0.183"),
        var_95=Decimal("0.025"),
        sharpe=Decimal("1.48"),
        max_drawdown=Decimal("-0.152"),
        last_rebalanced=date(2026, 7, 1),
        status="active",
    ),
    "pf-tech": Portfolio(
        id="pf-tech",
        name="Fundo Tech Brasil",
        sector="technology",
        nav=Decimal("510_000_000"),
        volatility=Decimal("0.247"),
        var_95=Decimal("0.038"),
        sharpe=Decimal("0.92"),
        max_drawdown=Decimal("-0.218"),
        last_rebalanced=date(2026, 5, 20),
        status="active",
    ),
    "pf-retail": Portfolio(
        id="pf-retail",
        name="Fundo Varejo Consumo",
        sector="retail",
        nav=Decimal("348_000_000"),
        volatility=Decimal("0.124"),
        var_95=Decimal("0.018"),
        sharpe=Decimal("1.13"),
        max_drawdown=Decimal("-0.104"),
        last_rebalanced=date(2026, 6, 28),
        status="active",
    ),
    "pf-healthcare": Portfolio(
        id="pf-healthcare",
        name="Fundo Saúde e Bem-Estar",
        sector="healthcare",
        nav=Decimal("282_000_000"),
        volatility=Decimal("0.143"),
        var_95=Decimal("0.020"),
        sharpe=Decimal("1.31"),
        max_drawdown=Decimal("-0.108"),
        last_rebalanced=date(2026, 7, 10),
        status="active",
    ),
    "pf-defunct": Portfolio(
        id="pf-defunct",
        name="Fundo Legado Inativo",
        sector="other",
        nav=Decimal("0"),
        volatility=Decimal("0"),
        var_95=Decimal("0"),
        sharpe=Decimal("0"),
        max_drawdown=Decimal("0"),
        last_rebalanced=date(2024, 1, 15),
        status="archived",
    ),
    "pf-extreme": Portfolio(
        id="pf-extreme",
        name="Fundo High Beta Oportunidades",
        sector="multi",
        nav=Decimal("95_000_000"),
        volatility=Decimal("0.382"),
        var_95=Decimal("0.062"),
        sharpe=Decimal("0.45"),
        max_drawdown=Decimal("-0.351"),
        last_rebalanced=date(2026, 4, 5),
        status="active",
    ),
}

HOLDINGS: dict[str, list[Holding]] = {
    "pf-finance": [
        Holding("ITUB4", "Itaú Unibanco PN", "finance", Decimal("0.25"), Decimal("312_500_000"), Decimal("0.183"), 245),
        Holding("BBDC4", "Bradesco PN", "finance", Decimal("0.20"), Decimal("250_000_000"), Decimal("0.152"), 230),
        Holding(
            "SANB11", "Santander Brasil UNT", "finance", Decimal("0.18"), Decimal("225_000_000"), Decimal("0.098"), 180
        ),
        Holding("BPAC11", "BTG Pactual UNT", "finance", Decimal("0.15"), Decimal("187_500_000"), Decimal("0.214"), 310),
        Holding(
            "BBAS3", "Banco do Brasil ON", "finance", Decimal("0.12"), Decimal("150_000_000"), Decimal("0.076"), 200
        ),
        Holding("CASH", "Caixa", "cash", Decimal("0.10"), Decimal("125_000_000"), Decimal("0.00"), 0),
    ],
    "pf-energy": [
        Holding("PETR4", "Petrobras PN", "energy", Decimal("0.30"), Decimal("262_500_000"), Decimal("0.245"), 365),
        Holding("ENGI11", "Engie Brasil UNT", "energy", Decimal("0.22"), Decimal("192_500_000"), Decimal("0.187"), 280),
        Holding("PRIO3", "PetroRio ON", "energy", Decimal("0.18"), Decimal("157_500_000"), Decimal("0.312"), 150),
        Holding("RAIZ4", "Raízen PN", "energy", Decimal("0.12"), Decimal("105_000_000"), Decimal("-0.043"), 90),
        Holding("CMIG4", "Cemig PN", "energy", Decimal("0.10"), Decimal("87_500_000"), Decimal("0.112"), 220),
        Holding("CASH", "Caixa", "cash", Decimal("0.08"), Decimal("70_000_000"), Decimal("0.00"), 0),
    ],
    "pf-tech": [
        Holding("TOTS3", "Totvs ON", "technology", Decimal("0.22"), Decimal("112_200_000"), Decimal("0.321"), 200),
        Holding(
            "BSSA3", "Brasil Software ON", "technology", Decimal("0.18"), Decimal("91_800_000"), Decimal("0.284"), 175
        ),
        Holding(
            "MELI34", "Mercado Livre DRN", "technology", Decimal("0.20"), Decimal("102_000_000"), Decimal("0.412"), 290
        ),
        Holding("CASH3", "Méliuz ON", "technology", Decimal("0.12"), Decimal("61_200_000"), Decimal("-0.087"), 60),
        Holding("LINX3", "Linx ON", "technology", Decimal("0.15"), Decimal("76_500_000"), Decimal("0.156"), 140),
        Holding("CASH", "Caixa", "cash", Decimal("0.13"), Decimal("66_300_000"), Decimal("0.00"), 0),
    ],
    "pf-retail": [
        Holding("LREN3", "Lojas Renner ON", "retail", Decimal("0.28"), Decimal("97_440_000"), Decimal("0.194"), 310),
        Holding("VVAR3", "Vivara ON", "retail", Decimal("0.20"), Decimal("69_600_000"), Decimal("0.267"), 185),
        Holding("MGLU3", "Magazine Luiza ON", "retail", Decimal("0.15"), Decimal("52_200_000"), Decimal("-0.124"), 45),
        Holding("NTCO3", "Natura ON", "retail", Decimal("0.18"), Decimal("62_640_000"), Decimal("0.083"), 160),
        Holding("AMER3", "Americanas ON", "retail", Decimal("0.07"), Decimal("24_360_000"), Decimal("-0.350"), 30),
        Holding("CASH", "Caixa", "cash", Decimal("0.12"), Decimal("41_760_000"), Decimal("0.00"), 0),
    ],
    "pf-healthcare": [
        Holding("QUAL3", "Qualicorp ON", "healthcare", Decimal("0.25"), Decimal("70_500_000"), Decimal("0.142"), 220),
        Holding("FLRY3", "Fleury ON", "healthcare", Decimal("0.22"), Decimal("62_040_000"), Decimal("0.175"), 195),
        Holding("HAPV3", "Hapvida ON", "healthcare", Decimal("0.18"), Decimal("50_760_000"), Decimal("0.098"), 140),
        Holding("ODON3", "Odontoprev ON", "healthcare", Decimal("0.15"), Decimal("42_300_000"), Decimal("0.210"), 260),
        Holding("DASA3", "Dasa ON", "healthcare", Decimal("0.10"), Decimal("28_200_000"), Decimal("-0.055"), 80),
        Holding("CASH", "Caixa", "cash", Decimal("0.10"), Decimal("28_200_000"), Decimal("0.00"), 0),
    ],
    "pf-defunct": [],
    "pf-extreme": [
        Holding("PRIO3", "PetroRio ON", "energy", Decimal("0.30"), Decimal("28_500_000"), Decimal("0.450"), 90),
        Holding("MGLU3", "Magazine Luiza ON", "retail", Decimal("0.20"), Decimal("19_000_000"), Decimal("-0.280"), 25),
        Holding(
            "MELI34", "Mercado Livre DRN", "technology", Decimal("0.25"), Decimal("23_750_000"), Decimal("0.520"), 120
        ),
        Holding(
            "BOVA11", "iShares Ibovespa ETF", "multi", Decimal("0.15"), Decimal("14_250_000"), Decimal("0.089"), 200
        ),
        Holding("CASH", "Caixa", "cash", Decimal("0.10"), Decimal("9_500_000"), Decimal("0.00"), 0),
    ],
}

THESES: dict[str, list[Thesis]] = {
    "pf-finance": [
        Thesis(
            "ths-fin-001",
            "Itaú: Margem financeira impulsionada por juros altos",
            "active",
            Decimal("0.85"),
            Decimal("0.18"),
            "12m",
        ),
        Thesis(
            "ths-fin-002",
            "BTG Pactual: Crescimento em investment banking",
            "active",
            Decimal("0.75"),
            Decimal("0.22"),
            "12m",
        ),
        Thesis(
            "ths-fin-003",
            "BB: Recuperação do crédito agrícola",
            "under_review",
            Decimal("0.60"),
            Decimal("0.10"),
            "6m",
        ),
        Thesis(
            "ths-fin-004",
            "Bradesco: Turnaround operacional pós-reestruturação",
            "draft",
            Decimal("0.55"),
            Decimal("0.12"),
            "18m",
        ),
    ],
    "pf-energy": [
        Thesis(
            "ths-ene-001",
            "Petrobras: Geração de caixa com petróleo acima do breakeven",
            "active",
            Decimal("0.90"),
            Decimal("0.25"),
            "12m",
        ),
        Thesis(
            "ths-ene-002",
            "Engie: Expansão renovável com contratos de longo prazo",
            "active",
            Decimal("0.80"),
            Decimal("0.14"),
            "24m",
        ),
        Thesis(
            "ths-ene-003",
            "PetroRio: Aquisições aumentando reservas",
            "monitoring",
            Decimal("0.70"),
            Decimal("0.30"),
            "12m",
        ),
        Thesis(
            "ths-ene-004",
            "Raízen: Margem de biocombustíveis comprimida",
            "draft",
            Decimal("0.40"),
            Decimal("0.05"),
            "6m",
        ),
        Thesis(
            "ths-ene-005",
            "Cemig: Privatização parcial como catalisador",
            "under_review",
            Decimal("0.65"),
            Decimal("0.15"),
            "12m",
        ),
    ],
    "pf-tech": [
        Thesis(
            "ths-tec-001",
            "Totvs: Liderança em ERP com expansão de margem",
            "active",
            Decimal("0.80"),
            Decimal("0.20"),
            "12m",
        ),
        Thesis(
            "ths-tec-002",
            "Mercado Livre: Crescimento em e-commerce e fintech",
            "active",
            Decimal("0.85"),
            Decimal("0.35"),
            "12m",
        ),
        Thesis(
            "ths-tec-003",
            "Brasil Software: Consolidação setorial",
            "approved",
            Decimal("0.70"),
            Decimal("0.18"),
            "18m",
        ),
    ],
    "pf-retail": [
        Thesis(
            "ths-ret-001",
            "Renner: Ciclo de crédito positivo impulsiona vendas",
            "active",
            Decimal("0.75"),
            Decimal("0.16"),
            "12m",
        ),
        Thesis(
            "ths-ret-002",
            "Vivara: Expansão de lojas com alto ROI",
            "active",
            Decimal("0.80"),
            Decimal("0.22"),
            "12m",
        ),
        Thesis(
            "ths-ret-003",
            "Natura: Recuperação internacional e sinergias Avon",
            "monitoring",
            Decimal("0.55"),
            Decimal("0.08"),
            "24m",
        ),
        Thesis(
            "ths-ret-004",
            "Magalu: Virada digital ainda incerta",
            "draft",
            Decimal("0.30"),
            Decimal("-0.10"),
            "6m",
        ),
    ],
    "pf-healthcare": [
        Thesis(
            "ths-hlt-001",
            "Fleury: Consolidação diagnóstica com sinergias",
            "active",
            Decimal("0.78"),
            Decimal("0.17"),
            "12m",
        ),
        Thesis(
            "ths-hlt-002",
            "Qualicorp: Crescimento em PMEs",
            "active",
            Decimal("0.72"),
            Decimal("0.14"),
            "12m",
        ),
        Thesis(
            "ths-hlt-003",
            "Odontoprev: Base de beneficiários resiliente",
            "approved",
            Decimal("0.82"),
            Decimal("0.19"),
            "12m",
        ),
        Thesis(
            "ths-hlt-004",
            "Hapvida: Sinistralidade em normalização",
            "under_review",
            Decimal("0.60"),
            Decimal("0.12"),
            "12m",
        ),
        Thesis(
            "ths-hlt-005",
            "Dasa: Alavancagem requer desinvestimentos",
            "monitoring",
            Decimal("0.35"),
            Decimal("-0.05"),
            "6m",
        ),
    ],
    "pf-defunct": [],
    "pf-extreme": [
        Thesis(
            "ths-ext-001",
            "Alta concentração em ativos voláteis para retorno absoluto",
            "active",
            Decimal("0.50"),
            Decimal("0.35"),
            "6m",
        ),
        Thesis(
            "ths-ext-002",
            "Mercado Livre: Crescimento exponencial via fintech",
            "active",
            Decimal("0.65"),
            Decimal("0.45"),
            "12m",
        ),
    ],
}


@dataclass(frozen=True)
class GoldenPortfolioData:
    portfolios: dict[str, Portfolio]
    holdings: dict[str, list[Holding]]
    theses: dict[str, list[Thesis]]


def load_golden_portfolio() -> GoldenPortfolioData:
    return GoldenPortfolioData(
        portfolios=dict(PORTFOLIOS),
        holdings={k: list(v) for k, v in HOLDINGS.items()},
        theses={k: list(v) for k, v in THESES.items()},
    )


def get_portfolio(portfolio_id: str) -> Portfolio | None:
    return PORTFOLIOS.get(portfolio_id)


def get_holdings(portfolio_id: str) -> list[Holding]:
    return list(HOLDINGS.get(portfolio_id, []))


def get_theses(portfolio_id: str) -> list[Thesis]:
    return list(THESES.get(portfolio_id, []))


def portfolio_ids() -> list[str]:
    return list(PORTFOLIOS)


def sector_portfolios(sector: str) -> list[Portfolio]:
    return [p for p in PORTFOLIOS.values() if p.sector == sector]
