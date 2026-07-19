from __future__ import annotations

import argparse
import json
from pathlib import Path

from apps.api.main import app


def rendered_schema() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export or verify the canonical OpenAPI document")
    parser.add_argument("--output", type=Path, default=Path("web/openapi.json"))
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    rendered = rendered_schema()
    if arguments.check:
        if not arguments.output.exists() or arguments.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("OpenAPI snapshot is stale; run scripts/export_openapi.py")
        print(f"openapi-ok path={arguments.output}")
        return
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    print(f"openapi-written path={arguments.output}")


if __name__ == "__main__":
    main()
