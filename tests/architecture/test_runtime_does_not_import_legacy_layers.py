from pathlib import Path

FORBIDDEN = (
    "from database.",
    "import database.",
    "from agents.",
    "from portfolio.",
    "Base.metadata.create_all",
    "init_db()",
)


def test_runtime_entrypoints_use_canonical_architecture():
    root = Path(__file__).resolve().parents[2]
    entrypoints = (
        root / "src/apps/api/main.py",
        root / "src/apps/worker/main.py",
        root / "src/apps/scheduler/main.py",
    )
    for path in entrypoints:
        content = path.read_text(encoding="utf-8")
        violations = [token for token in FORBIDDEN if token in content]
        assert not violations, f"{path} still imports legacy runtime: {violations}"
