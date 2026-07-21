"""Backward-compatibility shim.

All models have been split into domain-specific modules:
- portfolio_mandates: StrategyMandate, ModelPortfolio
- portfolio_versions: InstitutionalPortfolioVersion, PortfolioVersionThesis,
  PortfolioVersionValuation, PositionSnapshot, CashSnapshot,
  PortfolioLedgerEntry, NavPublication
- portfolio_risk: InstitutionalRiskPolicy, InstitutionalRiskSnapshot,
  RiskBreach, RiskWaiver, StressScenario, StressResult
- portfolio_optimization: OptimizationRun, PortfolioApprovalEvidence,
  BacktestConfig, InstitutionalBacktestRun

Prefer importing from the specific submodules or from
``src.database.models`` directly.
"""

from .portfolio_mandates import ModelPortfolio, StrategyMandate
from .portfolio_optimization import (
    BacktestConfig,
    InstitutionalBacktestRun,
    OptimizationRun,
    PortfolioApprovalEvidence,
)
from .portfolio_risk import (
    InstitutionalRiskPolicy,
    InstitutionalRiskSnapshot,
    RiskBreach,
    RiskWaiver,
    StressResult,
    StressScenario,
)
from .portfolio_versions import (
    CashSnapshot,
    InstitutionalPortfolioVersion,
    NavPublication,
    PortfolioLedgerEntry,
    PortfolioVersionThesis,
    PortfolioVersionValuation,
    PositionSnapshot,
)

__all__ = [
    "BacktestConfig",
    "CashSnapshot",
    "InstitutionalBacktestRun",
    "InstitutionalPortfolioVersion",
    "InstitutionalRiskPolicy",
    "InstitutionalRiskSnapshot",
    "ModelPortfolio",
    "NavPublication",
    "OptimizationRun",
    "PortfolioApprovalEvidence",
    "PortfolioLedgerEntry",
    "PortfolioVersionThesis",
    "PortfolioVersionValuation",
    "PositionSnapshot",
    "RiskBreach",
    "RiskWaiver",
    "StrategyMandate",
    "StressResult",
    "StressScenario",
]
