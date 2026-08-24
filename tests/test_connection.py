import asyncio

import pytest

from src.connection.manager import ConnectionManager
from tests.conftest import FakeWebSocket


@pytest.mark.anyio
async def test_connection_lifecycle_and_messages():
    first = FakeWebSocket()
    second = FakeWebSocket()

    await ConnectionManager.connect(first)
    await ConnectionManager.send_message(first, {"value": 1})
    await ConnectionManager.broadcast([first, second], {"value": 2})
    await ConnectionManager.disconnect(first)
    await ConnectionManager.disconnect(second, error=True)

    assert first.accepted
    assert first.sent == [{"value": 1}, {"value": 2}]
    assert second.sent == [{"value": 2}]
    assert first.closed and first.close_code == 1000
    assert not second.closed


@pytest.mark.anyio
async def test_closed_socket_does_not_break_message_or_broadcast():
    class ClosedWebSocket(FakeWebSocket):
        async def send_json(self, message):
            raise RuntimeError("Cannot call send once a close message has been sent")

        async def close(self, code=1000):
            raise RuntimeError("Socket is already closed")

    closed = ClosedWebSocket()
    active = FakeWebSocket()

    assert await ConnectionManager.send_message(closed, {"value": 1}) is False
    assert await ConnectionManager.disconnect(closed) is False
    assert await ConnectionManager.send_message(None, {"value": 1}) is False
    assert await ConnectionManager.disconnect(None) is False
    await ConnectionManager.broadcast([closed, active], {"value": 2})

    assert active.sent == [{"value": 2}]


@pytest.mark.anyio
async def test_broadcast_sends_to_clients_concurrently():
    both_started = asyncio.Event()
    started = 0

    class WaitingWebSocket(FakeWebSocket):
        async def send_json(self, message):
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=0.1)
            await super().send_json(message)

    first = WaitingWebSocket()
    second = WaitingWebSocket()
    await ConnectionManager.broadcast([first, second], {"value": 3})

    assert first.sent == second.sent == [{"value": 3}]
