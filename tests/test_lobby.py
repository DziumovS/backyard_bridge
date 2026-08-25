import pytest
import asyncio

from src.connection.manager import ConnectionManager
from src.lobby.handlers import LobbyHandlers
from src.lobby.manager import LobbyManager
from src.lobby.models import Lobby
from src.user.models import Player, User
from src.bot.factory import BotFactory
from src.bot.models import BotPlayer, BotUser
from src.lobby.errors import LobbyActionError
from tests.conftest import FakeWebSocket


def test_lobby_model(users):
    lobby = Lobby("abc", users[0], is_public=True, max_players=2)
    assert lobby.name == "Player 1's lobby"
    assert lobby.is_public
    assert lobby.max_players == 2
    assert not lobby.is_full
    assert lobby.get_summary() == {
        "lobby_id": "abc",
        "name": "Player 1's lobby",
        "players": 1,
        "max_players": 2,
    }
    assert lobby.is_host(users[0].user_id)
    assert not lobby.is_host(users[1].user_id)
    lobby.add_user(users[1])
    assert lobby.is_full
    assert lobby.get_user(users[1].user_id) is users[1]
    assert lobby.get_user("missing") is None
    assert lobby.get_users() == [
        {"user_id": "1", "user_name": "Player 1", "is_bot": False},
        {"user_id": "2", "user_name": "Player 2", "is_bot": False},
    ]
    assert lobby.get_users_websocket() == [users[0].websocket, users[1].websocket]
    players = lobby.create_player_list()
    assert all(isinstance(player, Player) for player in players)
    lobby.remove_user("missing")
    lobby.remove_user(users[1].user_id)
    assert list(lobby.users) == [users[0].user_id]
    with pytest.raises(ValueError, match="between 2 and 4"):
        Lobby("invalid", users[0], max_players=1)


def test_lobby_manager_lookup_and_id(users, monkeypatch):
    manager = LobbyManager(ConnectionManager())
    first = Lobby("taken", users[0])
    manager.add_lobby(first)
    values = iter(["taken", "free"])
    monkeypatch.setattr("src.lobby.manager.secrets.token_hex", lambda _: next(values))
    assert manager.generate_lobby_id() == "free"
    assert manager.get_lobby("taken") is first
    assert manager.get_lobby("missing") is None
    assert manager.get_lobby_by_user_id(users[0].user_id) is first
    assert manager.get_lobby_by_user_id("missing") is None
    public = Lobby("public", users[1], is_public=True, max_players=3)
    full_public = Lobby("full", users[2], is_public=True, max_players=2)
    full_public.add_user(users[3])
    private = Lobby("private", users[3], max_players=2)
    manager.add_lobby(public)
    manager.add_lobby(full_public)
    manager.add_lobby(private)
    assert manager.get_public_lobbies() == [public.get_summary()]
    public.in_game = True
    assert manager.get_public_lobbies() == []
    manager.remove_lobby(first.lobby_id)
    assert manager.get_lobby_by_user_id(users[0].user_id) is None


@pytest.mark.anyio
async def test_create_join_start_and_disconnect_lobby(users):
    manager = LobbyManager(ConnectionManager())
    manager.generate_lobby_id = lambda: "lobby"
    host, guest = users[:2]

    await manager.handlers.handle_create_lobby(
        host,
        host.websocket,
        is_public=True,
        max_players=2,
    )
    lobby = manager.get_lobby("lobby")
    assert lobby is not None
    assert lobby.name == "Player 1's lobby"
    assert lobby.is_public and lobby.max_players == 2
    assert host.websocket.sent[0]["lobby_name"] == lobby.name
    assert host.websocket.sent[1]["max_players"] == 2
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
    manager.add_lobby(lobby)

    await manager.handlers.handle_disconnect_lobby(users[0].user_id, error=True)

    assert users[1].websocket.sent == [{"type": "sg", "lobby_id": "lobby"}]
    assert users[1].websocket.closed
    assert not users[0].websocket.closed


@pytest.mark.anyio
async def test_host_can_start_and_close_lobby_with_server_only_bots(users):
    manager = LobbyManager(ConnectionManager())
    lobby = Lobby("lobby", users[0])
    lobby.add_user(BotUser("bot", "Alex Bot"))
    lobby.in_game = True
    manager.add_lobby(lobby)

    await manager.handlers.handle_disconnect_lobby(users[0].user_id)

    assert manager.get_lobby("lobby") is None
    assert users[0].websocket.closed


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
    manager.add_lobby(lobby)

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
    manager.add_lobby(lobby)

    await asyncio.gather(
        manager.handlers.handle_disconnect_lobby(users[1].user_id, error=True),
        manager.handlers.handle_disconnect_lobby(users[1].user_id, error=True),
    )

    assert list(lobby.users) == [users[0].user_id]


@pytest.mark.anyio
async def test_disconnect_unknown_user_is_noop():
    handlers = LobbyHandlers(LobbyManager(ConnectionManager()))
    await handlers.handle_disconnect_lobby("missing")


@pytest.mark.anyio
async def test_host_adds_bots_until_lobby_is_full(users):
    manager = LobbyManager(ConnectionManager())
    manager.bot_factory = BotFactory(
        names=("Alex", "Taylor", "Jordan"),
        chooser=lambda names: names[0],
    )
    lobby = Lobby("lobby", users[0])
    manager.add_lobby(lobby)

    with pytest.raises(LobbyActionError, match="Only the host"):
        await manager.handlers.handle_add_bot(users[1].user_id)

    for expected_size in (2, 3, 4):
        await manager.handlers.handle_add_bot(users[0].user_id)
        assert len(lobby.users) == expected_size

    bots = [user for user in lobby.users.values() if user.is_bot]
    assert [bot.user_name for bot in bots] == ["Alex Bot", "Taylor Bot", "Jordan Bot"]
    assert all(bot.websocket is None for bot in bots)
    assert all(isinstance(player, BotPlayer) for player in lobby.create_player_list()[1:])
    assert len(lobby.get_users_websocket()) == 1

    with pytest.raises(LobbyActionError, match="full"):
        await manager.handlers.handle_add_bot(users[0].user_id)

    lobby.in_game = True
    lobby.remove_user(bots[-1].user_id)
    with pytest.raises(LobbyActionError, match="full"):
        await manager.handlers.handle_add_bot(users[0].user_id)


@pytest.mark.anyio
async def test_only_host_can_kick_humans_and_bots(users):
    manager = LobbyManager(ConnectionManager())
    host, guest = users[:2]
    lobby = Lobby("lobby", host)
    manager.add_lobby(lobby)
    manager.add_user(lobby, guest)
    bot = BotUser("bot", "Alex Bot")
    manager.add_user(lobby, bot)

    with pytest.raises(LobbyActionError, match="Only the host"):
        await manager.handlers.handle_kick_user(guest.user_id, bot.user_id)
    with pytest.raises(LobbyActionError, match="cannot remove themselves"):
        await manager.handlers.handle_kick_user(host.user_id, host.user_id)
    with pytest.raises(LobbyActionError, match="no longer"):
        await manager.handlers.handle_kick_user(host.user_id, "missing")

    await manager.handlers.handle_kick_user(host.user_id, bot.user_id)
    assert lobby.get_user(bot.user_id) is None
    assert manager.get_lobby_by_user_id(bot.user_id) is None

    guest.websocket.sent.clear()
    await manager.handlers.handle_kick_user(host.user_id, guest.user_id)
    assert guest.websocket.sent == [
        {"type": "kfl", "msg": "The host removed you from the lobby."}
    ]
    assert guest.websocket.closed
    assert lobby.get_user(guest.user_id) is None
    assert host.websocket.sent[-1] == {"type": "tsb", "enable": False}


@pytest.mark.anyio
async def test_kick_is_rejected_after_game_starts(users):
    manager = LobbyManager(ConnectionManager())
    lobby = Lobby("lobby", users[0])
    manager.add_lobby(lobby)
    manager.add_user(lobby, users[1])
    lobby.in_game = True

    with pytest.raises(LobbyActionError, match="after the game starts"):
        await manager.handlers.handle_kick_user(users[0].user_id, users[1].user_id)
