from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ia_investing.orchestration.outbox_consumer import LogPublisher, OutboxConsumer


class FakeSession:
    def __init__(self, events=None):
        self._events = events or []
        self._published = []
        self._committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def execute(self, query):
        class Result:
            def __init__(self, events):
                self._events = events

            def scalars(self):
                return self

            def all(self):
                return self._events

        return Result(self._events)

    async def commit(self):
        self._committed = True


class FakeEvent:
    def __init__(self, event_type="TestEvent", payload=None, correlation_id=None):
        self.id = uuid4()
        self.event_type = event_type
        self.payload = payload or {"key": "value"}
        self.correlation_id = correlation_id or uuid4()
        self.occurred_at = datetime.now(UTC)
        self.published_at = None


@pytest.mark.asyncio
async def test_outbox_consumer_publishes_unpublished_events():
    event = FakeEvent()
    session = FakeSession(events=[event])
    publisher = AsyncMock()

    def session_factory():
        return session
    consumer = OutboxConsumer(session_factory, publisher, poll_interval_seconds=0.01, batch_size=10)

    published = await consumer._poll_once()

    assert published == 1
    publisher.publish.assert_called_once_with(
        event_type="TestEvent",
        payload={"key": "value"},
        correlation_id=str(event.correlation_id),
    )


@pytest.mark.asyncio
async def test_outbox_consumer_skips_empty_batch():
    session = FakeSession(events=[])
    publisher = AsyncMock()

    consumer = OutboxConsumer(lambda: session, publisher, batch_size=10)
    published = await consumer._poll_once()

    assert published == 0
    publisher.publish.assert_not_called()


@pytest.mark.asyncio
async def test_outbox_consumer_handles_publish_failure():
    good_event = FakeEvent(event_type="GoodEvent")
    bad_event = FakeEvent(event_type="BadEvent")
    session = FakeSession(events=[bad_event, good_event])
    publisher = AsyncMock()
    publisher.publish.side_effect = [
        RuntimeError("publish failed"),
        None,
    ]

    consumer = OutboxConsumer(lambda: session, publisher, batch_size=10)
    published = await consumer._poll_once()

    assert published == 1


@pytest.mark.asyncio
async def test_log_publisher_outputs_to_logger(caplog):
    publisher = LogPublisher()
    with caplog.at_level("INFO"):
        await publisher.publish("TestEvent", {"key": "value"}, "corr-123")
    assert "TestEvent" in caplog.text
    assert "corr-123" in caplog.text


def test_log_publisher_is_valid_event_publisher():
    publisher = LogPublisher()
    assert hasattr(publisher, "publish")
