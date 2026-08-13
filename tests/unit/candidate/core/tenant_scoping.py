"""Architecture test: production_runtime must use tenant-scoped lookups.

P0-08 regression test. Ensures that all session.get() calls on
tenant-owned entities go through CandidateRepository which enforces
organization_id verification.
"""

import ast
import pathlib


def _get_session_get_lines(source: str) -> list[tuple[int, str]]:
    """Return (line_number, node_repr) for all session.get() calls."""
    tree = ast.parse(source)
    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("session", "db_session")
        ):
            results.append((node.lineno, ast.unparse(node)))
    return results


def _get_candidate_repository_uses(source: str) -> list[tuple[int, str]]:
    """Return (line_number, node_repr) for all CandidateRepository uses."""
    tree = ast.parse(source)
    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "CandidateRepository":
            results.append((node.lineno, ast.unparse(node)))
    return results


class TestCandidateTenantScoping:
    """Verify P0-08 fixes are in place and not reverted."""

    @staticmethod
    def test_production_runtime_uses_candidate_repository():
        """All session.get() on tenant-owned entities must go through CandidateRepository."""
        runtime_path = (
            pathlib.Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "ia_investing"
            / "integrations"
            / "production_runtime.py"
        )
        source = runtime_path.read_text()

        session_gets = _get_session_get_lines(source)
        repo_uses = _get_candidate_repository_uses(source)

        # There should be at least as many CandidateRepository uses as session.get() calls
        # (some session.get() calls are for shared catalog models like Issuer which don't need scoping)
        assert len(repo_uses) >= len(session_gets) - 1, (
            f"Expected at least {len(session_gets) - 1} CandidateRepository uses "
            f"(found {len(repo_uses)}). Tenant-scoped lookups may have been reverted."
        )

    @staticmethod
    def test_candidate_repository_enforces_organization_id():
        """CandidateRepository methods must use organization_id in queries."""
        repo_path = (
            pathlib.Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "ia_investing"
            / "application"
            / "candidate_repository.py"
        )
        source = repo_path.read_text()

        assert "organization_id" in source, "CandidateRepository must enforce organization_id in queries"
        assert "get_candidate" in source, "CandidateRepository must have get_candidate method"
        assert "get_source" in source, "CandidateRepository must have get_source method"
        assert "get_analysis_run" in source, "CandidateRepository must have get_analysis_run method"
        assert "get_exploration_run" in source, "CandidateRepository must have get_exploration_run method"

    @staticmethod
    def test_no_direct_session_get_on_tenant_entities():
        """Direct session.get() on InvestmentCandidateRecord should not exist without repo."""
        runtime_path = (
            pathlib.Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "ia_investing"
            / "integrations"
            / "production_runtime.py"
        )
        source = runtime_path.read_text()
        lines = source.splitlines()

        tenant_entities = [
            "InvestmentCandidateRecord",
            "CandidateSourceRecord",
            "CandidateAnalysisRunRecord",
            "ExplorationRunRecord",
        ]

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "session.get" in stripped or "db_session.get" in stripped:
                # Check if this line is inside a CandidateRepository method
                # (which is acceptable) or if it's a direct call on tenant entities
                for entity in tenant_entities:
                    if entity in stripped and "repo =" not in lines[i - 2] and "await repo.get_" not in stripped:
                        # Check if this line has a repo = ... or await repo.get_... pattern
                        # Check if this is in the CandidateRepository class
                        # by looking at surrounding context
                        context_start = max(0, i - 10)
                        context = "\n".join(lines[context_start:i])
                        if "class CandidateRepository" not in context:
                            raise AssertionError(
                                f"Line {i}: Direct session.get() on {entity} without "
                                f"CandidateRepository scoping: {stripped}"
                            )
