from __future__ import annotations

import sys

from pydantic import ValidationError

from .settings import Settings


def check_config() -> None:
    """Validate configuration without printing values or secrets."""
    try:
        settings = Settings()
    except ValidationError as exc:
        locations = sorted({".".join(str(part) for part in error["loc"]) or "root" for error in exc.errors()})
        print("Configuration invalid: " + ", ".join(locations), file=sys.stderr)
        raise SystemExit(1) from None
    print(f"Configuration valid for environment={settings.application.environment}")
