from __future__ import annotations

import asyncio
import logging

from temporal_schedules import reconcile_configured_schedules

logger = logging.getLogger(__name__)


def main() -> None:
    results = asyncio.run(reconcile_configured_schedules())
    for schedule_id, result in results.items():
        logger.info("schedule=%s result=%s", schedule_id, result)


if __name__ == "__main__":
    main()
