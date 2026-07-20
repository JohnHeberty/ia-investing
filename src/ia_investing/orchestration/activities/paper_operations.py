from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from temporalio import activity
from temporalio.exceptions import ApplicationError

from database.core import session_scope
from ia_investing.application.institutional_portfolio import InstitutionalPortfolioService
from ia_investing.application.paper_execution import PaperExecutionService
from ia_investing.application.portfolio import BackendPortfolioOptimizationService
from ia_investing.domain.identity import InstitutionalAccessContext
from ia_investing.orchestration.activities._telemetry import activity_span


@activity.defn(name="reconcile_paper_portfolio")
async def reconcile_paper_portfolio(portfolio_id: str, organization_id: str, as_of: str) -> dict[str, object]:
    with activity_span("reconcile_paper_portfolio") as correlation_id:
        try:
            portfolio_uuid = UUID(portfolio_id)
            organization_uuid = UUID(organization_id)
            cutoff = datetime.fromisoformat(as_of)
        except ValueError as exc:
            raise ApplicationError(
                "invalid paper reconciliation input", type="DataValidationError", non_retryable=True
            ) from exc
        context = InstitutionalAccessContext(
            subject="service:paper-reconciliation",
            organization_id=organization_uuid,
            team_ids=frozenset(),
            permissions=frozenset({"reconciliation:write"}),
            environment="paper",
        )
        correlation_uuid = (
            UUID(correlation_id)
            if correlation_id
            else uuid5(NAMESPACE_URL, f"paper-reconciliation:{portfolio_id}:{as_of}")
        )
        async with session_scope() as session:
            try:
                rows = await PaperExecutionService(session).reconcile_portfolio(
                    portfolio_uuid, as_of=cutoff, context=context, correlation_id=correlation_uuid
                )
            except (LookupError, PermissionError, ValueError) as exc:
                raise ApplicationError(str(exc), type="DataValidationError", non_retryable=True) from exc
        return {
            "portfolio_id": portfolio_id,
            "as_of": as_of,
            "break_count": len(rows),
            "blocking_count": sum(row.blocking for row in rows),
            "environment": "paper",
        }


@activity.defn(name="publish_paper_nav")
async def publish_paper_nav(portfolio_version_id: str, organization_id: str, as_of: str) -> dict[str, object]:
    with activity_span("publish_paper_nav"):
        try:
            version_uuid = UUID(portfolio_version_id)
            organization_uuid = UUID(organization_id)
            cutoff = datetime.fromisoformat(as_of)
        except ValueError as exc:
            raise ApplicationError("invalid paper NAV input", type="DataValidationError", non_retryable=True) from exc
        context = InstitutionalAccessContext(
            subject="service:paper-valuation",
            organization_id=organization_uuid,
            team_ids=frozenset(),
            permissions=frozenset({"nav:publish", "organization:admin"}),
            environment="paper",
        )
        async with session_scope() as session:
            try:
                publication = await InstitutionalPortfolioService(session).publish_nav(version_uuid, cutoff, context)
            except (LookupError, PermissionError, ValueError) as exc:
                raise ApplicationError(str(exc), type="DataValidationError", non_retryable=True) from exc
        if not publication.reconciled:
            raise ApplicationError("paper NAV failed accounting reconciliation", type="ReconciliationError")
        return {
            "portfolio_id": str(publication.portfolio_id),
            "portfolio_version_id": portfolio_version_id,
            "nav_publication_id": str(publication.id),
            "as_of": as_of,
            "revision": publication.revision,
            "input_sha256": publication.input_sha256,
            "nav": str(publication.nav),
            "reconciled": publication.reconciled,
            "environment": "paper",
        }


@activity.defn(name="optimize_model_portfolio")
async def optimize_model_portfolio(portfolio_id: str, organization_id: str, as_of: str) -> dict[str, object]:
    """Run a backend-only optimization on the dedicated portfolio/risk worker."""
    with activity_span("optimize_model_portfolio"):
        try:
            portfolio_uuid = UUID(portfolio_id)
            organization_uuid = UUID(organization_id)
            cutoff = datetime.fromisoformat(as_of)
        except ValueError as exc:
            raise ApplicationError(
                "invalid portfolio optimization input", type="DataValidationError", non_retryable=True
            ) from exc
        context = InstitutionalAccessContext(
            subject="service:portfolio-optimizer",
            organization_id=organization_uuid,
            team_ids=frozenset(),
            permissions=frozenset({"portfolio:optimize", "organization:admin"}),
            environment="paper",
        )
        activity.heartbeat({"portfolio_id": portfolio_id, "state": "preparing_inputs"})
        async with session_scope() as session:
            try:
                run = await BackendPortfolioOptimizationService(session).optimize(portfolio_uuid, cutoff, context)
            except (LookupError, PermissionError, ValueError) as exc:
                raise ApplicationError(str(exc), type="DataValidationError", non_retryable=True) from exc
        activity.heartbeat({"portfolio_id": portfolio_id, "state": "persisted", "run_id": str(run.id)})
        return {
            "portfolio_id": portfolio_id,
            "optimization_run_id": str(run.id),
            "as_of": as_of,
            "input_sha256": run.input_sha256,
            "status": run.status,
            "solver": run.solver,
            "weights": run.weights,
            "diagnostics": run.diagnostics,
            "environment": "paper",
        }


PAPER_OPERATION_ACTIVITIES = (reconcile_paper_portfolio, publish_paper_nav, optimize_model_portfolio)
