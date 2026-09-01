import asyncio
import json

import pytest
import websockets
import httpx2
from fastapi.testclient import TestClient

from main import app
from src.bot.models import BotPlayer, BotUser
from src.connection.manager import ConnectionManager
from src.lobby.manager import LobbyManager
from src.lobby.models import Lobby
from src.lobby.router import game_manager, lobby_manager
from src.protocol import lobby_message_adapter
from src.user.models import Player, User
from tests.conftest import FakeWebSocket


@pytest.fixture(autouse=True)
def clear_router_state():
    lobby_manager.clear()
    game_manager.clear()
    yield
    lobby_manager.clear()
    game_manager.clear()


@pytest.mark.parametrize("is_public", [False, True], ids=["private", "public"])
@pytest.mark.parametrize("max_players", [2, 3, 4])
def test_every_supported_lobby_configuration(is_public, max_players):
    host = User("host", FakeWebSocket(), "Host")
    lobby = Lobby(
        "abcdef",
        host,
        is_public=is_public,
        max_players=max_players,
    )

    assert lobby.name == "Host's lobby"
    assert lobby.max_players == max_players
    assert lobby.is_public is is_public
    assert lobby.get_summary()["players"] == 1
    assert lobby.get_listing_summary()["is_private"] is (not is_public)
    assert ("lobby_id" in lobby.get_listing_summary()) is is_public

    for index in range(1, max_players):
        lobby.add_user(User(f"guest-{index}", FakeWebSocket(), f"Guest {index}"))
        assert lobby.is_full is (index + 1 == max_players)

    assert len(lobby.get_users()) == max_players
    assert sum(user["is_host"] for user in lobby.get_users()) == 1
    assert all(isinstance(player, Player) for player in lobby.create_player_list())


@pytest.mark.parametrize("max_players", [-1, 0, 1, 5, 10])
def test_every_unsupported_lobby_size_is_rejected(max_players):
    with pytest.raises(ValueError, match="between 2 and 4"):
        Lobby("abcdef", User("host", FakeWebSocket(), "Host"), max_players=max_players)


def test_mixed_human_and_bot_lobby_serialization():
    host = User("host", FakeWebSocket(), "Host")
    guest_without_socket = User("guest", None, "Guest")
    bot = BotUser("bot", "Alex Bot")
    lobby = Lobby("abcdef", host, max_players=3)
    lobby.add_user(guest_without_socket)
    lobby.add_user(bot)

    assert lobby.get_users_websocket() == [host.websocket]
    assert lobby.get_users() == [
        {"user_id": "host", "user_name": "Host", "is_bot": False, "is_host": True},
        {"user_id": "guest", "user_name": "Guest", "is_bot": False, "is_host": False},
        {"user_id": "bot", "user_name": "Alex Bot", "is_bot": True, "is_host": False},
    ]
    players = lobby.create_player_list()
    assert isinstance(players[0], Player)
    assert isinstance(players[1], Player)
    assert isinstance(players[2], BotPlayer)


def test_discovery_and_quick_play_follow_every_lobby_state():
    manager = LobbyManager(ConnectionManager())
    public_open = Lobby(
        "public-open", User("public-host", FakeWebSocket(), "Public"),
        is_public=True, max_players=3,
    )
    public_full = Lobby(
        "public-full", User("full-host", FakeWebSocket(), "Full"),
        is_public=True, max_players=2,
    )
    public_full.add_user(User("full-guest", FakeWebSocket(), "Guest"))
    public_started = Lobby(
        "public-started", User("started-host", FakeWebSocket(), "Started"),
        is_public=True,
    )
    public_started.in_game = True
    private_open = Lobby(
        "private-open", User("private-host", FakeWebSocket(), "Private"),
        is_public=False,
    )
    for lobby in (public_open, public_full, public_started, private_open):
        manager.add_lobby(lobby)

    assert manager.get_public_lobbies() == [public_open.get_summary()]
    assert manager.get_quick_play_lobby() == public_open.get_summary()
    assert manager.get_available_lobbies() == [
        public_open.get_listing_summary(),
        private_open.get_listing_summary(),
    ]

    public_open.in_game = True
    assert manager.get_public_lobbies() == []
    assert manager.get_quick_play_lobby() is None
    assert manager.get_available_lobbies() == [private_open.get_listing_summary()]

    manager.clear()
    assert manager.lobbies == {}
    assert manager.get_lobby_by_user_id("public-host") is None
    manager.remove_lobby("missing")


def test_check_lobby_tracks_open_full_started_and_removed_states():
    client = TestClient(app)
    host = User("host", FakeWebSocket(), "Host")
    lobby = Lobby("abcdef", host, max_players=2)
    lobby_manager.add_lobby(lobby)

    assert client.get("/check_lobby/abcdef").json()["exists"] is True
    lobby_manager.add_user(lobby, User("guest", FakeWebSocket(), "Guest"))
    assert client.get("/check_lobby/abcdef").json()["exists"] is False
    lobby_manager.remove_user(lobby, "guest")
    lobby.in_game = True
    assert client.get("/check_lobby/abcdef").json()["exists"] is False
    lobby_manager.remove_lobby("abcdef")
    assert client.get("/check_lobby/abcdef").json() == {
        "exists": False,
        "msg": "The lobby doesn't exist or is full.",
    }


@pytest.mark.parametrize(
    ("payload", "message_type"),
    [
        ({"type": "crl", "user_name": "Host"}, "crl"),
        ({"type": "crl", "user_name": "Host", "is_public": True, "max_players": 2}, "crl"),
        ({"type": "jl", "user_name": "Guest", "lobby_id": "abcdef"}, "jl"),
        ({"type": "jl", "user_name": "Guest", "lobby_id": "abcdef", "private_only": True}, "jl"),
        ({"type": "cll"}, "cll"),
        ({"type": "cll", "lobby_id": "abcdef"}, "cll"),
        ({"type": "sg"}, "sg"),
        ({"type": "ab"}, "ab"),
        ({"type": "ku", "user_id": "guest"}, "ku"),
    ],
)
def test_every_supported_lobby_message_shape(payload, message_type):
    message = lobby_message_adapter.validate_python(payload)
    assert message.type == message_type


@pytest.mark.anyio
async def test_guest_departure_preserves_lobby_and_host_departure_removes_it():
    manager = LobbyManager(ConnectionManager())
    host = User("host", FakeWebSocket(), "Host")
    guest = User("guest", FakeWebSocket(), "Guest")
    lobby = Lobby("abcdef", host, is_public=True, max_players=3)
    manager.add_lobby(lobby)
    manager.add_user(lobby, guest)

    await manager.handlers.handle_disconnect_lobby(guest.user_id)
    assert manager.get_lobby("abcdef") is lobby
    assert lobby.get_user(guest.user_id) is None
    assert guest.websocket.closed
    assert host.websocket.sent[-2]["type"] == "uu"
    assert host.websocket.sent[-1] == {"type": "tsb", "enable": False}

    replacement = User("replacement", FakeWebSocket(), "Replacement")
    await manager.handlers.handle_join_lobby(replacement, replacement.websocket, "abcdef")
    assert replacement.user_id in lobby.users

    manager._lobby_ids_by_user["ghost"] = lobby.lobby_id
    await manager.handlers.handle_disconnect_lobby("ghost")
    assert manager.get_lobby("abcdef") is lobby

    await manager.handlers.handle_disconnect_lobby(host.user_id)
    assert manager.get_lobby("abcdef") is None
    assert replacement.websocket.sent[-1]["type"] == "lcl"
    assert replacement.websocket.closed


async def _receive_json(socket):
    return json.loads(await asyncio.wait_for(socket.recv(), timeout=3))


@pytest.mark.e2e
@pytest.mark.anyio
@pytest.mark.parametrize("is_public", [False, True], ids=["private", "public"])
@pytest.mark.parametrize("max_players", [2, 3, 4])
async def test_lobby_websocket_creation_matrix(live_server, is_public, max_players):
    ws_base = live_server.replace("http://", "ws://")
    async with websockets.connect(f"{ws_base}/ws/lobby/matrix-host") as host:
        await host.send(json.dumps({
            "type": "crl",
            "user_name": "Matrix Host",
            "is_public": is_public,
            "max_players": max_players,
        }))
        session = await _receive_json(host)
        created = await _receive_json(host)
        users = await _receive_json(host)
        start_state = await _receive_json(host)

        assert session["type"] == "sid"
        assert created == {
            "type": "lcr",
            "lobby_id": created["lobby_id"],
            "lobby_name": "Matrix Host's lobby",
            "is_public": is_public,
            "max_players": max_players,
            "msg": "You created Matrix Host's lobby",
        }
        assert users["type"] == "uu"
        assert users["max_players"] == max_players
        assert users["is_host"] is True
        assert users["users"] == [{
            "user_id": session["user_id"],
            "user_name": "Matrix Host",
            "is_bot": False,
            "is_host": True,
        }]
        assert start_state == {"type": "tsb", "enable": False}

        listing = httpx2.get(f"{live_server}/lobbies").json()
        assert listing == [{
            **({"lobby_id": created["lobby_id"]} if is_public else {}),
            "name": "Matrix Host's lobby",
            "players": 1,
            "max_players": max_players,
            "is_private": not is_public,
        }]
