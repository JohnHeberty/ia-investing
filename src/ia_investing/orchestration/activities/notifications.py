from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="publish_event")
def publish_event(event_type: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps({"event_type": event_type, "payload": payload}, sort_keys=True, default=str)
    event_id = hashlib.sha256(canonical.encode()).hexdigest()
    logger.info("event_id=%s event_type=%s", event_id, event_type)
    return event_id


NOTIFICATION_ACTIVITIES = (publish_event,)
