#!/usr/bin/env python3
"""Fail-fast architecture checks for ia-investing.

This script intentionally checks composition, not only file existence. It is safe to
run without third-party dependencies:

    python scripts/check_architecture.py
    python scripts/check_architecture.py --strict
    python scripts/check_architecture.py --json

In report mode findings are printed and the command exits zero. In strict mode any
ERROR exits non-zero, making it suitable for CI once the migration branch is ready.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str
    remediation: str


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def add(
    findings: list[Finding],
    severity: str,
    code: str,
    path: Path,
    message: str,
    remediation: str,
) -> None:
    findings.append(
        Finding(
            severity=severity,
            code=code,
            path=path.as_posix(),
            message=message,
            remediation=remediation,
        )
    )


def check(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    src = root / "src"

    local_agents = src / "agents"
    if local_agents.exists():
        add(
            findings,
            "ERROR",
            "ARCH-001",
            local_agents,
            "Top-level package 'agents' shadows the external OpenAI Agents SDK package.",
            "Move all local agent code to ia_investing.ai, update imports, then delete src/agents.",
        )

    for legacy_name in ("database", "workflows", "connectors", "domain", "portfolio", "backtesting"):
        legacy = src / legacy_name
        canonical = src / "ia_investing" / legacy_name
        if legacy.exists() and canonical.exists():
            add(
                findings,
                "WARNING",
                "ARCH-002",
                legacy,
                f"Duplicate legacy and canonical namespaces exist for '{legacy_name}'.",
                "Choose ia_investing as the only production namespace and remove the compatibility copy after rewiring entrypoints.",
            )

    pyproject = root / "pyproject.toml"
    pyproject_text = read_text(pyproject)
    if 'include = ["*"]' in pyproject_text or "include = ['*']" in pyproject_text:
        add(
            findings,
            "ERROR",
            "PKG-001",
            pyproject,
            "Setuptools discovers every top-level package under src, including legacy/shadowing packages.",
            "After entrypoint migration, include only ia_investing* and apps*; explicitly exclude legacy roots.",
        )

    api_main = src / "apps" / "api" / "main.py"
    api_factory = src / "apps" / "api" / "app_factory.py"
    api_text = read_text(api_main) + read_text(api_factory)
    if api_main.exists():
        if "from database." in api_text or "from workflows" in api_text:
            add(
                findings,
                "ERROR",
                "API-001",
                api_main,
                "API entrypoint imports legacy namespaces instead of canonical ia_investing modules.",
                "Create a canonical application factory and route registry backed by ia_investing.application/domain/platform.",
            )
        if "oidc" not in api_text.lower() and "current_user" not in api_text.lower() and "auth" not in api_text.lower():
            add(
                findings,
                "ERROR",
                "SEC-001",
                api_main,
                "No authentication/authorization dependency is composed at the API entrypoint.",
                "Enforce OIDC authentication globally and apply RBAC+ABAC policies per command/query.",
            )
        if "telemetry" not in api_text.lower() and "instrument" not in api_text.lower():
            add(
                findings,
                "WARNING",
                "OBS-001",
                api_main,
                "Telemetry is configured elsewhere but not visibly initialized in the API entrypoint.",
                "Initialize OpenTelemetry before serving requests and instrument FastAPI, HTTPX and SQLAlchemy.",
            )
        factory_text = read_text(api_factory)
        has_factory = "def create_app" in factory_text and "_ROUTERS" in factory_text
        included_routers = len(re.findall(r"app\.include_router\(", api_text))
        route_files = list((src / "apps" / "api" / "routes").glob("*.py"))
        meaningful_route_files = [p for p in route_files if p.name != "__init__.py"]
        if meaningful_route_files and not has_factory and included_routers < len(meaningful_route_files):
            add(
                findings,
                "ERROR",
                "API-002",
                api_main,
                f"Only {included_routers} routers are composed, but {len(meaningful_route_files)} route modules exist.",
                "Use an explicit versioned route registry and test that every intended router is mounted exactly once.",
            )

    worker_main = src / "apps" / "worker" / "main.py"
    worker_text = read_text(worker_main)
    if worker_main.exists():
        if "activities=" not in worker_text:
            add(
                findings,
                "ERROR",
                "TMP-001",
                worker_main,
                "Temporal Worker registers workflows without registering activities.",
                "Build capability-specific worker registries containing exact workflows and activities for each task queue.",
            )
        if "from database." in worker_text or "from workflows" in worker_text:
            add(
                findings,
                "ERROR",
                "TMP-002",
                worker_main,
                "Worker entrypoint imports legacy namespaces.",
                "Wire workers to ia_investing.orchestration and canonical settings.",
            )
        if "settings.worker.capability" not in worker_text:
            add(
                findings,
                "WARNING",
                "TMP-003",
                worker_main,
                "Canonical worker capability setting is not used to select task queues/registries.",
                "Resolve one capability registry per process and fail startup for unknown/empty registries.",
            )

    scheduler_main = src / "apps" / "scheduler" / "main.py"
    scheduler_text = read_text(scheduler_main)
    if scheduler_main.exists():
        if "while True" in scheduler_text or "_last_run" in scheduler_text:
            add(
                findings,
                "ERROR",
                "TMP-004",
                scheduler_main,
                "In-memory scheduler is non-durable and loses state on restart.",
                "Provision Temporal Schedules declaratively and remove the scheduler process.",
            )
        if "Workflow()" in scheduler_text or "workflow class loaded" in scheduler_text:
            add(
                findings,
                "ERROR",
                "TMP-005",
                scheduler_main,
                "Scheduler instantiates workflow classes/logs instead of starting Temporal workflow executions.",
                "Use Temporal Client.start_workflow or, preferably, Temporal Schedules with overlap/catch-up policies.",
            )

    readme = root / "README.md"
    readme_text = read_text(readme)
    if "domain/" in readme_text and not readme_text.startswith("# ia-investing\n\nPlataforma de pesquisa"):
        add(
            findings,
            "WARNING",
            "DOC-001",
            readme,
            "README may not reflect the current repository layout.",
            "Rewrite architecture, setup, test, frontend and worker sections from executable commands.",
        )

    workflows_dir = root / ".github" / "workflows"
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    if not workflow_files:
        add(
            findings,
            "ERROR",
            "CI-001",
            workflows_dir,
            "No CI workflow exists to enforce tests, migrations, type checks, frontend build or security gates.",
            "Restore required GitHub Actions checks and protect main from direct unverified changes.",
        )

    entrypoints_with_settings = [
        ("API app factory", src / "apps" / "api" / "app_factory.py"),
        ("API security", src / "apps" / "api" / "security.py"),
        ("API dependencies", src / "apps" / "api" / "dependencies.py"),
        ("API health route", src / "apps" / "api" / "routes" / "health.py"),
        ("API schedules route", src / "apps" / "api" / "routes" / "schedules.py"),
        ("Worker main", src / "apps" / "worker" / "main.py"),
        ("Scheduler main", src / "apps" / "scheduler" / "main.py"),
        ("Agent runner", src / "ia_investing" / "ai" / "_runner.py"),
    ]
    for name, path in entrypoints_with_settings:
        text = read_text(path)
        if not text:
            continue
        if "from ia_investing.settings import" not in text:
            add(
                findings,
                "ERROR",
                "SET-001",
                path,
                f"{name} does not import settings from canonical ia_investing.settings.",
                "Replace legacy imports (e.g. from database.config) with 'from ia_investing.settings import Settings, get_settings'.",
            )
        if "from database.config import" in text or "from database import" in text:
            add(
                findings,
                "ERROR",
                "SET-002",
                path,
                f"{name} imports settings via legacy database.config shim.",
                "Replace 'from database.config import ...' with 'from ia_investing.settings import ...'.",
            )

    production_src = src / "ia_investing"
    if production_src.exists():
        for path in production_src.rglob("*.py"):
            text = read_text(path)
            if re.search(r"\bsynthetic\b", text, flags=re.IGNORECASE) and "test" not in path.parts:
                add(
                    findings,
                    "WARNING",
                    "DATA-001",
                    path,
                    "Production package contains synthetic-data references.",
                    "Tag data origin explicitly and make production readiness fail when synthetic-only calibration is active.",
                )

    return sorted(findings, key=lambda item: ({"ERROR": 0, "WARNING": 1, "INFO": 2}[item.severity], item.code, item.path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    findings = check(root)

    if args.json:
        print(json.dumps([asdict(item) for item in findings], ensure_ascii=False, indent=2))
    else:
        if not findings:
            print("Architecture checks passed.")
        for item in findings:
            print(f"[{item.severity}] {item.code} {item.path}")
            print(f"  {item.message}")
            print(f"  Fix: {item.remediation}")

        counts = {level: sum(item.severity == level for item in findings) for level in ("ERROR", "WARNING", "INFO")}
        print(f"Summary: {counts['ERROR']} errors, {counts['WARNING']} warnings, {counts['INFO']} info")

    if args.strict and any(item.severity == "ERROR" for item in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
