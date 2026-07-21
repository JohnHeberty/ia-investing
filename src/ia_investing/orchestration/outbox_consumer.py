from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import update

from database.models.research import DomainOutboxEvent

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    async def publish(self, event_type: str, payload: dict[str, Any], correlation_id: str) -> None: ...


class OutboxConsumer:
    """Polls unpublished DomainOutboxEvent rows and relays them to an external publisher."""

    def __init__(
        self,
        session_factory: Any,
        publisher: EventPublisher,
        *,
        poll_interval_seconds: float = 5.0,
        batch_size: int = 50,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        logger.info("outbox_consumer started poll_interval=%.1fs batch_size=%d", self._poll_interval, self._batch_size)
        while self._running:
            try:
                published = await self._poll_once()
                if published == 0:
                    await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("outbox_consumer poll error")
                await asyncio.sleep(self._poll_interval)
        logger.info("outbox_consumer stopped")

    async def _poll_once(self) -> int:
        async with self._session_factory() as session:
            result = await session.execute(select_domain_outbox_unpublished(self._batch_size))
            events = list(result.scalars().all())
            if not events:
                return 0

            published_count = 0
            for event in events:
                try:
                    await self._publisher.publish(
                        event_type=event.event_type,
                        payload=event.payload,
                        correlation_id=str(event.correlation_id),
                    )
                    await session.execute(
                        update(DomainOutboxEvent)
                        .where(DomainOutboxEvent.id == event.id)
                        .values(published_at=datetime.now(UTC))
                    )
                    published_count += 1
                except Exception:
                    logger.exception("Failed to publish event %s", event.id)

            await session.commit()
            logger.debug("outbox_consumer published %d/%d events", published_count, len(events))
            return published_count

    def stop(self) -> None:
        self._running = False


def select_domain_outbox_unpublished(batch_size: int):
    from sqlalchemy import select

    return (
        select(DomainOutboxEvent)
        .where(DomainOutboxEvent.published_at.is_(None))
        .order_by(DomainOutboxEvent.occurred_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )


class LogPublisher:
    """Default publisher that logs events — suitable for development and testing."""

    async def publish(self, event_type: str, payload: dict[str, Any], correlation_id: str) -> None:
        logger.info(
            "outbox event type=%s correlation_id=%s payload_keys=%s",
            event_type,
            correlation_id,
            list(payload.keys()),
        )
