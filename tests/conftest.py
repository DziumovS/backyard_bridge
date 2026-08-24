import asyncio
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterable

import httpx2
import pytest

from src.deck.models import Card
from src.game.models import Game
from src.user.models import Player, User


class FakeWebSocket:
    def __init__(self, incoming: Iterable[dict] = ()):
        self.incoming = list(incoming)
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000):
        self.closed = True
        self.close_code = code

    async def send_json(self, message):
        self.sent.append(message)

    async def receive_json(self):
        if not self.incoming:
            await asyncio.Future()
        value = self.incoming.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


@pytest.fixture
def fake_ws():
    return FakeWebSocket()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def live_server():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["BACKYARD_BRIDGE_BOT_ACTION_DELAY"] = "0"
    server_code = (
        "import random, uvicorn; "
        "random.seed(20260823); "
        f"uvicorn.run('main:app', host='127.0.0.1', port={port}, log_level='warning')"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", server_code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if httpx2.get(base_url, timeout=0.25).status_code == 200:
                break
        except httpx2.HTTPError:
            time.sleep(0.05)
    else:
        process.terminate()
        raise RuntimeError("The E2E server did not start")

    yield base_url
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.fixture
def users():
    return [User(str(index), FakeWebSocket(), f"Player {index}") for index in range(1, 5)]


@pytest.fixture
def players():
    return [Player(str(index), FakeWebSocket(), f"Player {index}") for index in range(1, 5)]


@pytest.fixture
def game(players, monkeypatch):
    monkeypatch.setattr("src.deck.models.shuffle", lambda cards: None)
    monkeypatch.setattr("src.game.models.random.shuffle", lambda values: None)
    return Game("game-1", players[:2])


def card(rank="9", suit="♠"):
    return Card(rank, suit)
