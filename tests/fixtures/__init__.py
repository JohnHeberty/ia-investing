from tests.fixtures.golden_ai_vectors import (
    AI_TEST_VECTORS,
    AITestVector,
    ai_scenario_names,
    load_ai_test_vector,
)
from tests.fixtures.golden_market import (
    CORPORATE_EVENTS,
    RISK_FREE_RATES,
    GoldenMarketData,
    load_golden_market,
)
from tests.fixtures.golden_portfolios import (
    HOLDINGS,
    THESES,
    GoldenPortfolioData,
    Holding,
    Portfolio,
    Thesis,
    get_holdings,
    get_portfolio,
    get_theses,
    load_golden_portfolio,
    portfolio_ids,
    sector_portfolios,
)
from tests.fixtures.golden_users import USERS, User, get_user_by_role

__all__ = [
    "AI_TEST_VECTORS",
    "CORPORATE_EVENTS",
    "HOLDINGS",
    "RISK_FREE_RATES",
    "THESES",
    "USERS",
    "AITestVector",
    "GoldenMarketData",
    "GoldenPortfolioData",
    "Holding",
    "Portfolio",
    "Thesis",
    "User",
    "ai_scenario_names",
    "get_holdings",
    "get_portfolio",
    "get_theses",
    "get_user_by_role",
    "load_ai_test_vector",
    "load_golden_market",
    "load_golden_portfolio",
    "portfolio_ids",
    "sector_portfolios",
]


def load_golden_portfolio_data(
    portfolio_id: str | None = None,
) -> GoldenPortfolioData:
    return load_golden_portfolio()
