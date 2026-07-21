"""Stock Intelligence — FastAPI application entry point."""

from __future__ import annotations

from apps.api.app_factory import create_app

app = create_app()
