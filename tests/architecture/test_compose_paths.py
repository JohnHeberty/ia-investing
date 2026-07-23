from pathlib import Path


def test_backend_image_uses_lockfile():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY pyproject.toml uv.lock README.md" in dockerfile
    assert "uv sync --frozen" in dockerfile
