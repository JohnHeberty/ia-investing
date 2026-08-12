from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ia_investing.application.paper_execution._evaluation import EvaluationService
from ia_investing.domain.identity import InstitutionalAccessContext


def _context(org_id: UUID | None = None, perms: frozenset[str] | None = None) -> InstitutionalAccessContext:
    org = org_id or uuid4()
    default_perms = frozenset({"postmortem:write", "portfolio:propose", "committee:vote"})
    resolved_perms = default_perms if perms is None else perms
    return InstitutionalAccessContext("manager", org, frozenset({uuid4()}), resolved_perms, "paper")


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.execute = AsyncMock(return_value=MagicMock())
    session.scalars = AsyncMock(return_value=MagicMock())
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    return session


def _mock_portfolio(
    organization_id: UUID | None = None,
    mandate_id: UUID | None = None,
    environment: str = "paper",
) -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.organization_id = organization_id or uuid4()
    p.mandate_id = mandate_id or uuid4()
    p.environment = environment
    return p


def _valid_post_mortem_attribution() -> dict[str, object]:
    return {
        "portfolio_version_id": str(uuid4()),
        "thesis_version_ids": [],
        "agent_run_ids": [],
        "decision": "buy",
        "trade_intent_ids": [],
        "attribution_by_asset": {},
        "attribution_by_sector": {},
        "attribution_by_factor": {},
        "decision_attribution": "0",
        "cost_attribution": "0",
        "comparison": {},
        "error_classification": "none",
        "corrective_actions": [],
    }


def _valid_comparison_config() -> dict[str, object]:
    return {
        "benchmark_id": str(uuid4()),
        "risk_policy_version": "v1",
        "cost_model_version": "v1",
        "window_type": "paper",
        "out_of_sample": True,
    }


class TestCreatePostMortem:
    @pytest.mark.asyncio
    async def test_raises_without_permission(self) -> None:
        session = _mock_session()
        ctx = _context(perms=frozenset())
        service = EvaluationService(session)
        with pytest.raises(PermissionError, match="postmortem:write"):
            await service.create_post_mortem(
                uuid4(),
                period_start=datetime(2026, 1, 1, tzinfo=UTC),
                period_end=datetime(2026, 6, 30, tzinfo=UTC),
                expected={},
                realized={},
                attribution=_valid_post_mortem_attribution(),
                findings=[],
                dissent=[],
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_raises_when_portfolio_not_found(self) -> None:
        session = _mock_session()
        session.get.return_value = None
        service = EvaluationService(session)
        with pytest.raises(LookupError, match="not found"):
            await service.create_post_mortem(
                uuid4(),
                period_start=datetime(2026, 1, 1, tzinfo=UTC),
                period_end=datetime(2026, 6, 30, tzinfo=UTC),
                expected={},
                realized={},
                attribution=_valid_post_mortem_attribution(),
                findings=[],
                dissent=[],
                context=_context(),
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_raises_on_naive_start(self) -> None:
        session = _mock_session()
        portfolio = _mock_portfolio()
        session.get.return_value = portfolio
        ctx = _context(portfolio.organization_id)
        service = EvaluationService(session)
        with pytest.raises(ValueError, match="timezone-aware window"):
            await service.create_post_mortem(
                portfolio.id,
                period_start=datetime(2026, 1, 1),
                period_end=datetime(2026, 6, 30, tzinfo=UTC),
                expected={},
                realized={},
                attribution=_valid_post_mortem_attribution(),
                findings=[],
                dissent=[],
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_raises_when_end_before_start(self) -> None:
        session = _mock_session()
        portfolio = _mock_portfolio()
        session.get.return_value = portfolio
        ctx = _context(portfolio.organization_id)
        service = EvaluationService(session)
        with pytest.raises(ValueError, match="timezone-aware window"):
            await service.create_post_mortem(
                portfolio.id,
                period_start=datetime(2026, 6, 30, tzinfo=UTC),
                period_end=datetime(2026, 1, 1, tzinfo=UTC),
                expected={},
                realized={},
                attribution=_valid_post_mortem_attribution(),
                findings=[],
                dissent=[],
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_raises_on_incomplete_lineage(self) -> None:
        session = _mock_session()
        portfolio = _mock_portfolio()
        session.get.return_value = portfolio
        ctx = _context(portfolio.organization_id)
        service = EvaluationService(session)
        with pytest.raises(ValueError, match="incomplete"):
            await service.create_post_mortem(
                portfolio.id,
                period_start=datetime(2026, 1, 1, tzinfo=UTC),
                period_end=datetime(2026, 6, 30, tzinfo=UTC),
                expected={},
                realized={},
                attribution={"missing": "fields"},
                findings=[],
                dissent=[],
                context=ctx,
                correlation_id=uuid4(),
            )


class TestDecideChallenger:
    @pytest.mark.asyncio
    async def test_raises_without_permission(self) -> None:
        session = _mock_session()
        ctx = _context(perms=frozenset())
        service = EvaluationService(session)
        with pytest.raises(PermissionError, match="committee:vote"):
            await service.decide_challenger(uuid4(), decision="retained", context=ctx, correlation_id=uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_evaluation_not_found(self) -> None:
        session = _mock_session()
        session.get.return_value = None
        service = EvaluationService(session)
        with pytest.raises(LookupError, match="not found"):
            await service.decide_challenger(uuid4(), decision="retained", context=_context(), correlation_id=uuid4())

    @pytest.mark.asyncio
    async def test_raises_on_invalid_decision(self) -> None:
        session = _mock_session()
        evaluation = MagicMock()
        evaluation.id = uuid4()
        evaluation.created_by = "other_user"
        evaluation.decision = "pending_committee"
        evaluation.champion_portfolio_id = uuid4()

        portfolio = _mock_portfolio(evaluation.champion_portfolio_id)

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "ChallengerEvaluation":
                return evaluation
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        ctx = _context(portfolio.organization_id)
        service = EvaluationService(session)
        with pytest.raises(ValueError, match="invalid challenger decision"):
            await service.decide_challenger(evaluation.id, decision="maybe", context=ctx, correlation_id=uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_already_decided(self) -> None:
        session = _mock_session()
        evaluation = MagicMock()
        evaluation.id = uuid4()
        evaluation.created_by = "other_user"
        evaluation.decision = "retained"
        evaluation.champion_portfolio_id = uuid4()

        portfolio = _mock_portfolio(evaluation.champion_portfolio_id)

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "ChallengerEvaluation":
                return evaluation
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        ctx = _context(portfolio.organization_id)
        service = EvaluationService(session)
        with pytest.raises(ValueError, match="already been decided"):
            await service.decide_challenger(evaluation.id, decision="promoted", context=ctx, correlation_id=uuid4())

    @pytest.mark.asyncio
    async def test_raises_on_four_eyes_violation(self) -> None:
        session = _mock_session()
        evaluation = MagicMock()
        evaluation.id = uuid4()
        evaluation.created_by = "manager"
        evaluation.decision = "pending_committee"
        evaluation.champion_portfolio_id = uuid4()

        portfolio = _mock_portfolio(evaluation.champion_portfolio_id)

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "ChallengerEvaluation":
                return evaluation
            if model.__name__ == "ModelPortfolio":
                return portfolio
            return None

        session.get = fake_get
        ctx = _context(portfolio.organization_id)
        service = EvaluationService(session)
        with pytest.raises(PermissionError, match="own"):
            await service.decide_challenger(evaluation.id, decision="retained", context=ctx, correlation_id=uuid4())


class TestCreateChallengerEvaluation:
    @pytest.mark.asyncio
    async def test_raises_without_permission(self) -> None:
        session = _mock_session()
        ctx = _context(perms=frozenset())
        service = EvaluationService(session)
        with pytest.raises(PermissionError, match="portfolio:propose"):
            await service.create_challenger_evaluation(
                champion_portfolio_id=uuid4(),
                challenger_portfolio_id=uuid4(),
                window_start=datetime(2026, 1, 1, tzinfo=UTC),
                window_end=datetime(2026, 6, 30, tzinfo=UTC),
                methodology_version="v1",
                comparison_config=_valid_comparison_config(),
                metrics={},
                evidence={},
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_raises_when_portfolios_not_found(self) -> None:
        session = _mock_session()
        session.get.return_value = None
        service = EvaluationService(session)
        with pytest.raises(LookupError, match="not found"):
            await service.create_challenger_evaluation(
                champion_portfolio_id=uuid4(),
                challenger_portfolio_id=uuid4(),
                window_start=datetime(2026, 1, 1, tzinfo=UTC),
                window_end=datetime(2026, 6, 30, tzinfo=UTC),
                methodology_version="v1",
                comparison_config=_valid_comparison_config(),
                metrics={},
                evidence={},
                context=_context(),
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_raises_when_mandates_differ(self) -> None:
        session = _mock_session()
        org_id = uuid4()
        champion = _mock_portfolio(org_id, mandate_id=uuid4())
        challenger = _mock_portfolio(org_id, mandate_id=uuid4())

        async def fake_get(model, id_val, **kwargs):
            if id_val == champion.id:
                return champion
            if id_val == challenger.id:
                return challenger
            return None

        session.get = fake_get
        ctx = _context(org_id)
        service = EvaluationService(session)
        with pytest.raises(ValueError, match="same mandate"):
            await service.create_challenger_evaluation(
                champion_portfolio_id=champion.id,
                challenger_portfolio_id=challenger.id,
                window_start=datetime(2026, 1, 1, tzinfo=UTC),
                window_end=datetime(2026, 6, 30, tzinfo=UTC),
                methodology_version="v1",
                comparison_config=_valid_comparison_config(),
                metrics={},
                evidence={},
                context=ctx,
                correlation_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_raises_when_not_paper_only(self) -> None:
        session = _mock_session()
        org_id = uuid4()
        mandate_id = uuid4()
        champion = _mock_portfolio(org_id, mandate_id, environment="live")
        challenger = _mock_portfolio(org_id, mandate_id, environment="paper")

        async def fake_get(model, id_val, **kwargs):
            if id_val == champion.id:
                return champion
            if id_val == challenger.id:
                return challenger
            return None

        session.get = fake_get
        ctx = _context(org_id)
        service = EvaluationService(session)
        with pytest.raises(ValueError, match="paper-only"):
            await service.create_challenger_evaluation(
                champion_portfolio_id=champion.id,
                challenger_portfolio_id=challenger.id,
                window_start=datetime(2026, 1, 1, tzinfo=UTC),
                window_end=datetime(2026, 6, 30, tzinfo=UTC),
                methodology_version="v1",
                comparison_config=_valid_comparison_config(),
                metrics={},
                evidence={},
                context=ctx,
                correlation_id=uuid4(),
            )
