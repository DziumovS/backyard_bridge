import pytest
import asyncio

from src.connection.manager import ConnectionManager
from src.lobby.handlers import LobbyHandlers
from src.lobby.manager import LobbyManager
from src.lobby.models import Lobby
from src.user.models import Player, User
from tests.conftest import FakeWebSocket


def test_lobby_model(users):
    lobby = Lobby("abc", users[0])
    assert lobby.is_host(users[0].user_id)
    assert not lobby.is_host(users[1].user_id)
    lobby.add_user(users[1])
    assert lobby.get_user(users[1].user_id) is users[1]
    assert lobby.get_user("missing") is None
    assert lobby.get_users() == [
        {"user_id": "1", "user_name": "Player 1"},
        {"user_id": "2", "user_name": "Player 2"},
    ]
    assert lobby.get_users_websocket() == [users[0].websocket, users[1].websocket]
    players = lobby.create_player_list()
    assert all(isinstance(player, Player) for player in players)
    lobby.remove_user("missing")
    lobby.remove_user(users[1].user_id)
    assert list(lobby.users) == [users[0].user_id]


def test_lobby_manager_lookup_and_id(users, monkeypatch):
    manager = LobbyManager(ConnectionManager())
    first = Lobby("taken", users[0])
    manager.lobbies[first.lobby_id] = first
    values = iter(["taken", "free"])
    monkeypatch.setattr("src.lobby.manager.secrets.token_hex", lambda _: next(values))
    assert manager.generate_lobby_id() == "free"
    assert manager.get_lobby("taken") is first
    assert manager.get_lobby("missing") is None
    assert manager.get_lobby_by_user_id(users[0].user_id) is first
    assert manager.get_lobby_by_user_id("missing") is None


@pytest.mark.anyio
async def test_create_join_start_and_disconnect_lobby(users):
    manager = LobbyManager(ConnectionManager())
    manager.generate_lobby_id = lambda: "lobby"
    host, guest = users[:2]

    await manager.handlers.handle_create_lobby(host, host.websocket)
    lobby = manager.get_lobby("lobby")
    assert lobby is not None
    assert [message["type"] for message in host.websocket.sent] == ["lcr", "uu", "tsb"]
    assert not host.websocket.sent[-1]["enable"]

    await manager.handlers.handle_join_lobby(guest, guest.websocket, "missing")
    assert guest.websocket.sent[-1]["type"] == "se"
    guest.websocket.sent.clear()
    await manager.handlers.handle_join_lobby(guest, guest.websocket, "lobby")
    assert guest.websocket.sent[0]["type"] == "jdl"
    assert host.websocket.sent[-1] == {"type": "tsb", "enable": True}

    game_id, players = await manager.handlers.handle_start_game(host.user_id)
    assert game_id == "lobby" and len(players) == 2
    assert await manager.handlers.handle_start_game("missing") is None

    await manager.handlers.handle_disconnect_lobby(guest.user_id)
    assert guest.websocket.closed
    assert list(lobby.users) == [host.user_id]
    assert host.websocket.sent[-1] == {"type": "tsb", "enable": False}

    await manager.handlers.handle_disconnect_lobby(host.user_id)
    assert manager.get_lobby("lobby") is None
    assert host.websocket.closed


@pytest.mark.anyio
async def test_host_disconnect_broadcasts_start(users):
    manager = LobbyManager(ConnectionManager())
    lobby = Lobby("lobby", users[0])
    lobby.add_user(users[1])
    lobby.in_game = True
    manager.lobbies[lobby.lobby_id] = lobby

    await manager.handlers.handle_disconnect_lobby(users[0].user_id, error=True)

    assert users[1].websocket.sent == [{"type": "sg", "lobby_id": "lobby"}]
    assert users[1].websocket.closed
    assert not users[0].websocket.closed


@pytest.mark.anyio
async def test_concurrent_lobby_disconnects_are_serialized(users):
    class SlowConnectionManager(ConnectionManager):
        @staticmethod
        async def broadcast(websockets, message):
            await asyncio.sleep(0)
            await ConnectionManager.broadcast(websockets, message)

    manager = LobbyManager(SlowConnectionManager())
    lobby = Lobby("lobby", users[0])
    lobby.add_user(users[1])
    lobby.in_game = True
    manager.lobbies[lobby.lobby_id] = lobby

    await asyncio.gather(
        manager.handlers.handle_disconnect_lobby(users[0].user_id, error=True),
        manager.handlers.handle_disconnect_lobby(users[1].user_id, error=True),
    )

    assert manager.get_lobby("lobby") is None


@pytest.mark.anyio
async def test_duplicate_concurrent_guest_disconnect_is_safe(users):
    class SlowConnectionManager(ConnectionManager):
        @staticmethod
        async def broadcast(websockets, message):
            await asyncio.sleep(0)
            await ConnectionManager.broadcast(websockets, message)

    manager = LobbyManager(SlowConnectionManager())
    lobby = Lobby("lobby", users[0])
    lobby.add_user(users[1])
    manager.lobbies[lobby.lobby_id] = lobby

    await asyncio.gather(
        manager.handlers.handle_disconnect_lobby(users[1].user_id, error=True),
        manager.handlers.handle_disconnect_lobby(users[1].user_id, error=True),
    )

    assert list(lobby.users) == [users[0].user_id]


@pytest.mark.anyio
async def test_disconnect_unknown_user_is_noop():
    handlers = LobbyHandlers(LobbyManager(ConnectionManager()))
    await handlers.handle_disconnect_lobby("missing")
