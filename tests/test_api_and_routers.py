import asyncio
import json
from unittest.mock import AsyncMock

import pytest
import websockets
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from main import app
from src.game.models import Game
from src.game.errors import InvalidAction
from src.game.router import websocket_game
from src.lobby.router import game_manager, lobby_manager, websocket_lobby
from src.lobby.errors import LobbyActionError
from src.user.models import Player
from tests.conftest import FakeWebSocket


@pytest.fixture(autouse=True)
def clear_global_state():
    lobby_manager.clear()
    game_manager.clear()
    yield
    lobby_manager.clear()
    game_manager.clear()


def test_http_endpoints():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Backyard Bridge" in response.text
    assert "Add Bot" in response.text
    assert "script.js" in response.text
    assert "user-scalable=no" not in response.text
    assert 'aria-live="polite"' in response.text
    assert "onclick=" not in response.text
    assert response.headers["content-security-policy"].startswith("default-src 'self'")
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert client.get("/health").json() == {"status": "ok"}

    rules = client.get("/rules")
    assert rules.status_code == 200 and "MAIN RULES" in rules.json()["rules"]
    missing = client.get("/check_lobby/missing").json()
    assert missing == {"exists": False, "msg": "The lobby doesn't exist or no slots."}
    cards = client.get("/get_cards")
    assert cards.status_code == 200
    assert "/static/cards/closed_card.png" in cards.json()
    assert cards.headers["cache-control"] == "public, max-age=86400"
    static_css = client.get("/static/css/styles.css", headers={"Accept-Encoding": "gzip"})
    assert static_css.status_code == 200
    assert static_css.headers["cache-control"] == "public, max-age=3600, must-revalidate"
    assert static_css.headers["content-encoding"] == "gzip"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.e2e
@pytest.mark.anyio
async def test_lobby_websocket_end_to_end(live_server):
    ws_base = live_server.replace("http://", "ws://")
    async with websockets.connect(f"{ws_base}/ws/lobby/host") as host:
        await host.send(json.dumps({"type": "crl", "user_name": "Host"}))
        session = await _receive_json(host)
        created = await _receive_json(host)
        users = await _receive_json(host)
        toggle = await _receive_json(host)
        lobby_id = created["lobby_id"]
        assert created["type"] == "lcr"
        assert session["type"] == "sid"
        assert users["users"] == [
            {"user_id": session["user_id"], "user_name": "Host", "is_bot": False}
        ]
        assert toggle == {"type": "tsb", "enable": False}

        async with websockets.connect(f"{ws_base}/ws/lobby/guest") as guest:
            await guest.send(json.dumps({"type": "jl", "user_name": "Guest", "lobby_id": lobby_id}))
            assert (await _receive_json(guest))["type"] == "sid"
            assert (await _receive_json(guest))["type"] == "jdl"
            assert (await _receive_json(guest))["type"] == "uu"
            assert (await _receive_json(host))["type"] == "uu"
            assert await _receive_json(host) == {"type": "tsb", "enable": True}
            await guest.send(json.dumps({"type": "cll"}))
            assert (await _receive_json(host))["type"] == "uu"
            assert await _receive_json(host) == {"type": "tsb", "enable": False}

        await host.send(json.dumps({"type": "cll"}))


@pytest.mark.e2e
@pytest.mark.anyio
async def test_host_kicks_human_and_bot_from_lobby(live_server):
    ws_base = live_server.replace("http://", "ws://")
    host = await websockets.connect(f"{ws_base}/ws/lobby/kick-host")
    guest = None
    try:
        await host.send(json.dumps({"type": "crl", "user_name": "Host"}))
        host_session = await _receive_json(host)
        created = await _receive_json(host)
        lobby_id = created["lobby_id"]
        await _receive_json(host)
        await _receive_json(host)

        await host.send('{"type":"ab"}')
        bot_update = await _receive_json(host)
        await _receive_json(host)
        bot_id = next(user["user_id"] for user in bot_update["users"] if user["is_bot"])

        guest = await websockets.connect(f"{ws_base}/ws/lobby/kick-guest")
        await guest.send(json.dumps({
            "type": "jl", "user_name": "Guest", "lobby_id": lobby_id,
        }))
        guest_session = await _receive_json(guest)
        await _receive_json(guest)
        await _receive_json(guest)
        await _receive_json(host)
        await _receive_json(host)

        await guest.send(json.dumps({"type": "ku", "user_id": bot_id}))
        assert await _receive_json(guest) == {
            "type": "se", "msg": "Only the host can remove players.",
        }

        await host.send(json.dumps({"type": "ku", "user_id": bot_id}))
        assert len((await _receive_json(host))["users"]) == 2
        assert await _receive_json(host) == {"type": "tsb", "enable": True}
        assert len((await _receive_json(guest))["users"]) == 2

        await host.send(json.dumps({"type": "ku", "user_id": guest_session["user_id"]}))
        assert await _receive_json(guest) == {
            "type": "kfl", "msg": "The host removed you from the lobby.",
        }
        assert len((await _receive_json(host))["users"]) == 1
        assert await _receive_json(host) == {"type": "tsb", "enable": False}

        await host.send(json.dumps({"type": "ku", "user_id": host_session["user_id"]}))
        assert await _receive_json(host) == {
            "type": "se", "msg": "The host cannot remove themselves.",
        }
    finally:
        if guest is not None:
            await guest.close()
        await host.close()


async def _receive_json(socket):
    return json.loads(await asyncio.wait_for(socket.recv(), timeout=3))


async def _create_started_lobby(ws_base, player_count):
    lobby_sockets = []
    sessions = []
    host = await websockets.connect(f"{ws_base}/ws/lobby/browser-host")
    lobby_sockets.append(host)
    await host.send(json.dumps({"type": "crl", "user_name": "Player 1"}))
    sessions.append(await _receive_json(host))
    created = await _receive_json(host)
    game_id = created["lobby_id"]
    await _receive_json(host)  # users update
    await _receive_json(host)  # disabled start button

    for index in range(2, player_count + 1):
        guest = await websockets.connect(f"{ws_base}/ws/lobby/browser-{index}")
        lobby_sockets.append(guest)
        await guest.send(json.dumps({
            "type": "jl", "user_name": f"Player {index}", "lobby_id": game_id,
        }))
        sessions.append(await _receive_json(guest))
        assert (await _receive_json(guest))["type"] == "jdl"
        update = await _receive_json(guest)
        assert update["type"] == "uu"
        assert len(update["users"]) == index
        for existing in lobby_sockets[:-1]:
            assert (await _receive_json(existing))["type"] == "uu"
        assert (await _receive_json(host)) == {"type": "tsb", "enable": True}

    return game_id, sessions, lobby_sockets


@pytest.mark.e2e
@pytest.mark.anyio
@pytest.mark.parametrize("player_count", [2, 3, 4])
async def test_host_can_play_with_bots_at_every_supported_player_count(live_server, player_count):
    ws_base = live_server.replace("http://", "ws://")
    lobby_socket = await websockets.connect(f"{ws_base}/ws/lobby/bot-host")
    game_socket = None
    try:
        await lobby_socket.send(json.dumps({"type": "crl", "user_name": "Host"}))
        session = await _receive_json(lobby_socket)
        created = await _receive_json(lobby_socket)
        game_id = created["lobby_id"]
        await _receive_json(lobby_socket)
        await _receive_json(lobby_socket)

        latest_users = []
        for expected_size in range(2, player_count + 1):
            await lobby_socket.send('{"type":"ab"}')
            update = await _receive_json(lobby_socket)
            toggle = await _receive_json(lobby_socket)
            assert update["type"] == "uu"
            assert toggle == {"type": "tsb", "enable": True}
            assert len(update["users"]) == expected_size
            latest_users = update["users"]

        assert sum(user["is_bot"] for user in latest_users) == player_count - 1
        assert all(user["user_name"].endswith(" Bot") for user in latest_users if user["is_bot"])

        if player_count == 4:
            await lobby_socket.send('{"type":"ab"}')
            assert await _receive_json(lobby_socket) == {"type": "se", "msg": "The lobby is full."}

        await lobby_socket.send('{"type":"sg"}')
        game_socket = await websockets.connect(
            f"{ws_base}/ws/game/{game_id}/{session['user_id']}"
        )
        await game_socket.send(json.dumps({"type": "auth", "token": session["session_token"]}))
        await game_socket.send('{"type":"gs"}')

        human_state = None
        for _ in range(200):
            message = await _receive_json(game_socket)
            if message["type"] == "gd":
                assert len(message["players"]) == player_count
                if message["current_player"]:
                    human_state = message
                    break
        assert human_state is not None
        assert len(human_state["hand"]) >= 5
    finally:
        if game_socket is not None:
            await game_socket.close()
        await lobby_socket.close()


async def _connect_game_clients(ws_base, game_id, sessions):
    sockets = await asyncio.gather(*[
        websockets.connect(f"{ws_base}/ws/game/{game_id}/{session['user_id']}")
        for session in sessions
    ])
    await asyncio.gather(*[
        socket.send(json.dumps({"type": "auth", "token": session["session_token"]}))
        for socket, session in zip(sockets, sessions)
    ])
    await asyncio.gather(*[socket.send('{"type":"gs"}') for socket in sockets])
    return dict(zip((session["user_id"] for session in sessions), sockets))


def _assert_synchronized(states):
    public_keys = (
        "deck_len", "chosen_suit", "current_card", "scores_rate", "scores_rate_changed", "round_over",
        "players_hands",
    )
    reference = states[next(iter(states))]
    for player_id, state in states.items():
        assert {key: state[key] for key in public_keys} == {
            key: reference[key] for key in public_keys
        }
        public_hand = next(
            player["hand_len"] for player in state["players_hands"] if player["player_id"] == player_id
        )
        assert len(state["hand"]) == public_hand


async def _collect_game_data(sockets):
    async def collect(socket):
        messages = []
        while True:
            message = await _receive_json(socket)
            messages.append(message)
            if message["type"] == "gd":
                return messages

    batches = dict(zip(sockets, await asyncio.gather(*[collect(socket) for socket in sockets.values()])))
    states = {player_id: messages[-1] for player_id, messages in batches.items()}
    _assert_synchronized(states)
    return states, batches


async def _advance_turn(sockets, states, current_id):
    for _ in range(30):
        state = states[current_id]
        options = state["player_options"]
        if options["must_draw"]:
            action = {"type": "dc"}
        elif options["must_skip"]:
            action = {"type": "st"}
        elif state["playable_cards"]:
            card = state["playable_cards"][0]
            action = {
                "type": "pc",
                "card": card,
                "chosen_suit": "♠" if card["rank"] == "J" else None,
            }
        elif options["can_draw"]:
            action = {"type": "dc"}
        elif options["can_skip"] or state["current_card"]["rank"] == "J":
            action = {"type": "st"}
        else:
            pytest.fail(f"Player {current_id} has no legal action: {state}")

        await sockets[current_id].send(json.dumps(action))
        states, batches = await _collect_game_data(sockets)
        turn_messages = [
            message for messages in batches.values() for message in messages if message["type"] == "wt"
        ]
        if turn_messages:
            next_ids = {message["current_player"] for message in turn_messages}
            assert len(next_ids) == 1
            return states, next_ids.pop()
        assert not states[current_id]["round_over"], "Round ended before a full turn rotation"
    pytest.fail("Turn did not advance after 30 legal actions")


@pytest.mark.e2e
@pytest.mark.anyio
@pytest.mark.parametrize("player_count", [2, 3, 4])
async def test_game_websocket_end_to_end_for_every_supported_player_count(live_server, player_count):
    ws_base = live_server.replace("http://", "ws://")
    game_id, sessions, lobby_sockets = await _create_started_lobby(ws_base, player_count)
    try:
        await lobby_sockets[1].send('{"type":"sg"}')
        rejected_start = await _receive_json(lobby_sockets[1])
        assert rejected_start == {"type": "se", "msg": "Only the host can start a full game."}

        if player_count == 4:
            fifth = await websockets.connect(f"{ws_base}/ws/lobby/fifth")
            try:
                assert (await _receive_json(fifth))["type"] == "sid"
                await fifth.send(json.dumps({
                    "type": "jl", "user_name": "Player 5", "lobby_id": game_id,
                }))
                refusal = await _receive_json(fifth)
                assert refusal["type"] == "se"
                assert "no slots" in refusal["msg"]
            finally:
                await fifth.close()

        await lobby_sockets[0].send('{"type":"sg"}')
        for guest in lobby_sockets[1:]:
            assert await _receive_json(guest) == {"type": "sg", "lobby_id": game_id}
        sockets = await _connect_game_clients(ws_base, game_id, sessions)
        states, batches = await _collect_game_data(sockets)
        current_ids = {
            message["current_player"]
            for messages in batches.values() for message in messages if message["type"] == "wt"
        }
        assert len(current_ids) == 1
        current_id = current_ids.pop()
        first_turn = await _receive_json(sockets[current_id])
        assert first_turn["type"] == "ft"
        assert all(len(state["hand"]) == 5 for state in states.values())

        duplicate_ready_id = next(player_id for player_id in sockets if player_id != current_id)
        await sockets[duplicate_ready_id].send('{"type":"gs"}')
        duplicate_ready = await _receive_json(sockets[duplicate_ready_id])
        assert duplicate_ready == {"type": "se", "msg": "This client is already ready."}

        first_card = first_turn["current_card"]
        await sockets[current_id].send(json.dumps({
            "type": "pc",
            "card": first_card,
            "chosen_suit": "♠" if first_card["rank"] == "J" else None,
        }))
        states, _ = await _collect_game_data(sockets)

        non_current = next(player_id for player_id in sockets if player_id != current_id)
        await sockets[non_current].send('{"type":"dc"}')
        assert (await _receive_json(sockets[non_current]))["type"] == "se"

        visited = [current_id]
        for _ in range(player_count):
            states, current_id = await _advance_turn(sockets, states, current_id)
            visited.append(current_id)
        assert len(set(visited[:-1])) == player_count
        assert visited[-1] == visited[0]
    finally:
        if "sockets" in locals():
            await asyncio.gather(*[socket.close() for socket in sockets.values()])
        await asyncio.gather(*[socket.close() for socket in lobby_sockets])


@pytest.mark.e2e
@pytest.mark.anyio
@pytest.mark.parametrize("player_count", [2, 3, 4])
async def test_game_waits_for_every_client_before_initializing(live_server, player_count):
    ws_base = live_server.replace("http://", "ws://")
    game_id, sessions, lobby_sockets = await _create_started_lobby(ws_base, player_count)
    sockets = {}
    try:
        await lobby_sockets[0].send('{"type":"sg"}')
        for guest in lobby_sockets[1:]:
            assert (await _receive_json(guest))["type"] == "sg"

        raw_sockets = await asyncio.gather(*[
            websockets.connect(f"{ws_base}/ws/game/{game_id}/{session['user_id']}")
            for session in sessions
        ])
        sockets = dict(zip((session["user_id"] for session in sessions), raw_sockets))
        await asyncio.gather(*[
            socket.send(json.dumps({"type": "auth", "token": session["session_token"]}))
            for socket, session in zip(raw_sockets, sessions)
        ])

        for socket in raw_sockets[:-1]:
            await socket.send('{"type":"gs"}')
        for socket in raw_sockets[:-1]:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(socket.recv(), timeout=0.1)

        await raw_sockets[-1].send('{"type":"gs"}')
        states, batches = await _collect_game_data(sockets)
        current_id = next(
            message["current_player"]
            for messages in batches.values() for message in messages if message["type"] == "wt"
        )
        assert (await _receive_json(sockets[current_id]))["type"] == "ft"
        assert all(len(state["players"]) == player_count for state in states.values())
    finally:
        await asyncio.gather(*[socket.close() for socket in sockets.values()])
        await asyncio.gather(*[socket.close() for socket in lobby_sockets])


@pytest.mark.e2e
@pytest.mark.anyio
@pytest.mark.parametrize("player_count", [2, 3, 4])
@pytest.mark.parametrize("disconnect_current", [False, True], ids=["non-current", "current"])
async def test_game_disconnects_for_every_supported_player_count(
    live_server, player_count, disconnect_current,
):
    ws_base = live_server.replace("http://", "ws://")
    game_id, sessions, lobby_sockets = await _create_started_lobby(ws_base, player_count)
    sockets = {}
    try:
        await lobby_sockets[0].send('{"type":"sg"}')
        for guest in lobby_sockets[1:]:
            assert (await _receive_json(guest))["type"] == "sg"
        sockets = await _connect_game_clients(ws_base, game_id, sessions)
        states, batches = await _collect_game_data(sockets)
        current_id = next(
            message["current_player"]
            for messages in batches.values() for message in messages if message["type"] == "wt"
        )
        assert (await _receive_json(sockets[current_id]))["type"] == "ft"
        target_id = current_id if disconnect_current else next(
            player_id for player_id in sockets if player_id != current_id
        )
        await sockets[target_id].close()

        remaining = {player_id: socket for player_id, socket in sockets.items() if player_id != target_id}
        states_after = {}
        announced_turns = set()
        for player_id, socket in remaining.items():
            assert (await _receive_json(socket)) == {"type": "lg", "player_id": target_id}
            assert (await _receive_json(socket))["type"] == "se"
            whose_turn = await _receive_json(socket)
            assert whose_turn["type"] == "wt"
            announced_turns.add(whose_turn["current_player"])
            state = await _receive_json(socket)
            assert state["type"] == "gd"
            states_after[player_id] = state

        assert len(announced_turns) == 1
        assert target_id not in announced_turns
        assert all(len(state["players_hands"]) == player_count - 1 for state in states_after.values())
        _assert_synchronized(states_after)

        if player_count == 2:
            for socket in remaining.values():
                assert (await _receive_json(socket))["type"] == "nep"
    finally:
        await asyncio.gather(*[socket.close() for socket in sockets.values()])
        await asyncio.gather(*[socket.close() for socket in lobby_sockets])


@pytest.mark.anyio
async def test_lobby_router_dispatches_all_events(monkeypatch):
    ws = FakeWebSocket(
        [
            {"type": "crl", "user_name": "Name"},
            {"type": "jl", "user_name": "Name", "lobby_id": "abcdef"},
            {"type": "ab"},
            {"type": "ku", "user_id": "other"},
            {"type": "sg"},
        ]
    )
    create = AsyncMock()
    join = AsyncMock()
    add_bot = AsyncMock()
    kick_user = AsyncMock()
    start = AsyncMock(
        return_value=(
            "game",
            [Player("user", FakeWebSocket(), "User"), Player("other", FakeWebSocket(), "Other")],
        )
    )
    disconnect = AsyncMock()
    monkeypatch.setattr(lobby_manager.handlers, "handle_create_lobby", create)
    monkeypatch.setattr(lobby_manager.handlers, "handle_join_lobby", join)
    monkeypatch.setattr(lobby_manager.handlers, "handle_add_bot", add_bot)
    monkeypatch.setattr(lobby_manager.handlers, "handle_kick_user", kick_user)
    monkeypatch.setattr(lobby_manager.handlers, "handle_start_game", start)
    monkeypatch.setattr(lobby_manager.handlers, "handle_disconnect_lobby", disconnect)

    await websocket_lobby(ws, "user")

    create.assert_awaited_once()
    join.assert_awaited_once()
    add_bot.assert_awaited_once()
    kick_user.assert_awaited_once()
    assert start.await_count == 1
    assert disconnect.await_count == 1
    assert game_manager.get_game("game") is not None


@pytest.mark.anyio
async def test_lobby_router_close_and_disconnect_codes(monkeypatch):
    disconnect = AsyncMock()
    monkeypatch.setattr(lobby_manager.handlers, "handle_disconnect_lobby", disconnect)
    monkeypatch.setattr(lobby_manager, "get_lobby_by_user_id", lambda user_id: object())
    await websocket_lobby(FakeWebSocket([{"type": "cll"}]), "user")
    assert disconnect.await_count == 1

    for code, called in [(1001, True), (1012, True), (1000, True)]:
        disconnect.reset_mock()
        await websocket_lobby(FakeWebSocket([WebSocketDisconnect(code)]), "user")
        assert disconnect.await_count == int(called)
        if called:
            assert disconnect.await_args.kwargs["error"] is True


@pytest.mark.anyio
async def test_game_router_dispatches_all_events(game, monkeypatch):
    game_manager.create_game(game)
    game.all_connected_event.set()
    other = game.players[1]
    game.mark_client_ready(other.user_id)
    game.mark_client_initialized(other.user_id)
    ws = FakeWebSocket(
        [
            {"type": "auth", "token": game.players[0].session_token},
            {"type": "gs"},
            {"type": "gs"},
            {"type": "pc", "card": {"rank": "9", "suit": "♠"}, "chosen_suit": None},
            {"type": "dc"},
            {"type": "st"},
            {"type": "smm"},
            {"type": "go"},
            {"type": "rg"},
            WebSocketDisconnect(1000),
        ]
    )
    handler = game_manager.event_handler
    methods = [
        "handle_game_started",
        "handle_played_card",
        "handle_drew_card",
        "handle_skip_turn",
        "handle_show_my_move",
        "handle_game_over",
        "handle_reset_game",
    ]
    mocks = {}
    for name in methods:
        mocks[name] = AsyncMock()
        monkeypatch.setattr(handler, name, mocks[name])
    monkeypatch.setattr(handler, "handle_disconnect_game", AsyncMock())
    monkeypatch.setattr(handler, "send_first_turn", AsyncMock())

    player = game.players[0]
    await websocket_game(ws, game.game_id, player.user_id)
    assert all(mock.await_count == 1 for mock in mocks.values())


@pytest.mark.anyio
async def test_game_router_disconnect_paths(game, monkeypatch):
    game_manager.create_game(game)
    game.all_connected_event.set()
    game.players[0].websocket = None
    disconnect_game = AsyncMock()
    disconnect = AsyncMock()
    monkeypatch.setattr(game_manager.event_handler, "handle_disconnect_game", disconnect_game)
    monkeypatch.setattr(game_manager.connection_manager, "disconnect", disconnect)

    await websocket_game(
        FakeWebSocket([
            {"type": "auth", "token": game.players[0].session_token},
            WebSocketDisconnect(1001),
        ]),
        game.game_id,
        game.players[0].user_id,
    )
    disconnect_game.assert_awaited_once_with(player_id=game.players[0].user_id, error=True)

    disconnect_game.reset_mock()
    game.players[0].websocket = None
    await websocket_game(
        FakeWebSocket([
            {"type": "auth", "token": game.players[0].session_token},
            WebSocketDisconnect(1012),
        ]),
        game.game_id,
        game.players[0].user_id,
    )
    assert disconnect_game.await_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("timeout_stage", ["connected", "ready", "initialized"])
async def test_game_router_aborts_each_startup_timeout(game, monkeypatch, timeout_stage):
    game_manager.create_game(game)
    player = game.players[0]
    incoming = [{"type": "auth", "token": player.session_token}]

    if timeout_stage == "connected":
        monkeypatch.setattr(game, "wait_until_all_ready", AsyncMock(return_value=False))
    else:
        game.all_connected_event.set()
        incoming.append({"type": "gs"})
        monkeypatch.setattr(
            game,
            "wait_until_all_clients_ready",
            AsyncMock(return_value=timeout_stage == "initialized"),
        )
        if timeout_stage == "initialized":
            monkeypatch.setattr(
                game,
                "wait_until_all_clients_initialized",
                AsyncMock(return_value=False),
            )

    websocket = FakeWebSocket(incoming)
    await websocket_game(websocket, game.game_id, player.user_id)

    assert websocket.sent[-1] == {"type": "se", "msg": "Game startup timed out. Please try again."}
    assert websocket.closed
    assert game_manager.get_game(game.game_id) is None


@pytest.mark.anyio
async def test_lobby_router_reports_protocol_and_start_errors(monkeypatch):
    ws = FakeWebSocket(
        [
            {"type": "invalid"},
            {"type": "ab"},
            {"type": "ku", "user_id": "other"},
            {"type": "sg"},
            WebSocketDisconnect(1000),
        ]
    )
    monkeypatch.setattr(
        lobby_manager.handlers,
        "handle_add_bot",
        AsyncMock(side_effect=LobbyActionError("Only the host can add a bot.")),
    )
    monkeypatch.setattr(
        lobby_manager.handlers,
        "handle_kick_user",
        AsyncMock(side_effect=LobbyActionError("Only the host can remove players.")),
    )
    monkeypatch.setattr(lobby_manager.handlers, "handle_start_game", AsyncMock(return_value=None))
    await websocket_lobby(ws, "untrusted-path-id")
    errors = [message for message in ws.sent if message["type"] == "se"]
    assert [message["msg"] for message in errors] == [
        "Invalid lobby message.",
        "Only the host can add a bot.",
        "Only the host can remove players.",
        "Only the host can start a full game.",
    ]


@pytest.mark.anyio
async def test_game_router_reports_protocol_and_action_errors(game, monkeypatch):
    game_manager.create_game(game)
    game.all_connected_event.set()
    player = game.players[0]
    ws = FakeWebSocket(
        [
            {"type": "auth", "token": player.session_token},
            {"type": "invalid"},
            {"type": "dc"},
            WebSocketDisconnect(1000),
        ]
    )
    monkeypatch.setattr(
        game_manager.event_handler,
        "handle_drew_card",
        AsyncMock(side_effect=InvalidAction("Rejected action.")),
    )
    monkeypatch.setattr(game_manager.event_handler, "handle_disconnect_game", AsyncMock())
    await websocket_game(ws, game.game_id, player.user_id)
    assert [message["msg"] for message in ws.sent] == ["Invalid game message.", "Rejected action."]
