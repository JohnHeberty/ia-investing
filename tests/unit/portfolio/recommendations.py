"""Unit tests for portfolio_recommendations routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from apps.api.routes.portfolio_recommendations import (
    PortfolioThesesResponse,
    PortfolioThesisItem,
    RecommendationResponse,
    router,
)
from apps.api.security import AuthContext, get_auth_context


def _mock_auth() -> AuthContext:
    return AuthContext(
        subject="test@example.com",
        roles=frozenset({"admin"}),
        permissions=frozenset({"portfolio:read"}),
        authentication_method="test",
        organization_id=uuid4(),
    )


@pytest.fixture()
def app_instance():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_auth_context] = _mock_auth
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app_instance):
    return TestClient(app_instance, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------
class TestSchemas:
    def test_recommendation_response(self) -> None:
        resp = RecommendationResponse(
            portfolio_id="p1",
            summary="Hold",
            overall_risk="medium",
            recommendations=[],
            risk_assessment={},
            performance_outlook={},
            key_risks=[],
            suggested_limits={},
            llm_analysis=None,
        )
        assert resp.portfolio_id == "p1"

    def test_portfolio_thesis_item(self) -> None:
        item = PortfolioThesisItem(
            thesis_id=uuid4(),
            thesis_status="active",
            version_id=uuid4(),
            version_number=1,
            version_status="approved",
            summary="Test thesis",
            recommendation="buy",
            recommendation_confidence=0.8,
            assumptions=[],
            catalysts=[],
            risks=[],
            invalidation_criteria=[],
            data_as_of=datetime.now(UTC),
            expires_at=datetime.now(UTC),
            created_by="user@test.com",
            approved_by=None,
            approved_at=None,
        )
        assert item.recommendation == "buy"

    def test_portfolio_theses_response(self) -> None:
        resp = PortfolioThesesResponse(portfolio_id="p1", theses=[], count=0)
        assert resp.count == 0


# ---------------------------------------------------------------------------
# Recommendations endpoint
# ---------------------------------------------------------------------------
class TestRecommendationsEndpoint:
    @pytest.mark.asyncio
    async def test_portfolio_not_found(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.portfolio_recommendations import get_portfolio_recommendations

        auth = _mock_auth()
        with pytest.raises(HTTPException) as exc_info:
            await get_portfolio_recommendations(
                portfolio_id=uuid4(),
                auth=auth,
                session=mock_session,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_positions(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid4(), "Test Portfolio", "BRL", None, None, None, None),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.portfolio_recommendations import get_portfolio_recommendations

        auth = _mock_auth()

        with (
            patch("ia_investing.market_data.get_current_prices", return_value={}),
            patch("apps.api.routes.portfolio_recommendations.compute_scores", new_callable=AsyncMock, return_value={}),
        ):
            result = await get_portfolio_recommendations(
                portfolio_id=uuid4(),
                auth=auth,
                session=mock_session,
            )
            assert result.portfolio_id is not None

    @pytest.mark.asyncio
    async def test_db_error_raises_500(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("db down"))

        from apps.api.routes.portfolio_recommendations import get_portfolio_recommendations

        auth = _mock_auth()
        with pytest.raises(HTTPException) as exc_info:
            await get_portfolio_recommendations(
                portfolio_id=uuid4(),
                auth=auth,
                session=mock_session,
            )
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Theses endpoint
# ---------------------------------------------------------------------------
class TestThesesEndpoint:
    @pytest.mark.asyncio
    async def test_empty_theses(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.portfolio_recommendations import get_portfolio_theses

        auth = _mock_auth()
        result = await get_portfolio_theses(portfolio_id=uuid4(), auth=auth, session=mock_session)
        assert result.count == 0

    @pytest.mark.asyncio
    async def test_with_theses(self) -> None:
        now = datetime.now(UTC)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (
                uuid4(),
                "active",
                uuid4(),
                1,
                "approved",
                "Summary",
                "buy",
                0.8,
                [],
                [],
                [],
                [],
                now,
                now,
                "user@test.com",
                None,
                None,
            ),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.portfolio_recommendations import get_portfolio_theses

        auth = _mock_auth()
        result = await get_portfolio_theses(portfolio_id=uuid4(), auth=auth, session=mock_session)
        assert result.count == 1

    @pytest.mark.asyncio
    async def test_db_error_raises_500(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("db down"))

        from apps.api.routes.portfolio_recommendations import get_portfolio_theses

        auth = _mock_auth()
        with pytest.raises(HTTPException) as exc_info:
            await get_portfolio_theses(portfolio_id=uuid4(), auth=auth, session=mock_session)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_null_confidence_defaults_to_zero(self) -> None:
        now = datetime.now(UTC)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (
                uuid4(),
                "active",
                uuid4(),
                1,
                "approved",
                "Summary",
                "buy",
                None,
                [],
                [],
                [],
                [],
                now,
                now,
                "",
                None,
                None,
            ),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.portfolio_recommendations import get_portfolio_theses

        auth = _mock_auth()
        result = await get_portfolio_theses(portfolio_id=uuid4(), auth=auth, session=mock_session)
        assert result.theses[0].recommendation_confidence == 0.0
