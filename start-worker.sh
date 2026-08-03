#!/usr/bin/env bash
set -euo pipefail
cd /root/ia-investing

export OTEL_EXPORTER_OTLP_ENDPOINT=""
export OTEL_TRACES_EXPORTER=none
export OTEL_METRICS_EXPORTER=none
export OTEL_LOGS_EXPORTER=none

exec uv run python -W ignore -c "
import warnings, sys, logging
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
from apps.worker.main import start_worker
import asyncio
asyncio.run(start_worker())
"
