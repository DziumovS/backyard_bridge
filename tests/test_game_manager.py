import pytest
import asyncio

from src.connection.manager import ConnectionManager
from src.game.manager import GameManager
from tests.conftest import FakeWebSocket


def test_game_manager_crud(game):
    manager = GameManager(ConnectionManager())
    assert manager.get_game("missing") is None
    manager.create_game(game)
    assert manager.get_game(game.game_id) is game
    assert manager.get_game_by_player_id(game.players[0].user_id) is game
    assert manager.get_game_by_player_id("missing") is None
    manager.remove_game("missing")
    manager.remove_game(game.game_id)
    assert manager.games == {}


def test_game_manager_keeps_player_index_in_sync(game, players):
    manager = GameManager(ConnectionManager())
    manager.create_game(game)
    extra = players[2]

    manager.add_player(game, extra)
    assert manager.get_game_by_player_id(extra.user_id) is game

    manager.remove_player(game, extra)
    assert manager.get_game_by_player_id(extra.user_id) is None

    manager.clear()
    assert manager.games == {}
    assert manager.get_game_by_player_id(game.players[0].user_id) is None


def test_removing_player_preserves_current_player(game, players):
    manager = GameManager(ConnectionManager())
    manager.create_game(game)
    manager.add_player(game, players[2])
    game.current_player_index = 2
    current_player = game.get_current_player()

    manager.remove_player(game, game.players[0])

    assert game.get_current_player() is current_player


@pytest.mark.anyio
async def test_game_manager_sends_turn_and_private_state(game):
    manager = GameManager(ConnectionManager())
    player = game.players[0]
    player.websocket = FakeWebSocket()
    game.current_card = player.hand[0]
    await manager.send_whose_turn(player.websocket, "Your turn", player.user_id)
    await manager.send_game_data(player, True, game)

    assert player.websocket.sent[0] == {
        "type": "wt",
        "msg": "Your turn",
        "current_player": player.user_id,
    }
    state = player.websocket.sent[1]
    assert state["type"] == "gd"
    assert state["hand"] == player.hand_to_dict()
    assert state["current_player"] is True
    assert state["deck_len"] == len(game.deck)
    assert state["scores_rate"] == "x1"
    assert state["scores_rate_changed"] is False

    await manager.send_game_data(player, True, game, scores_rate_changed=True)
    assert player.websocket.sent[-1]["scores_rate_changed"] is True


@pytest.mark.anyio
async def test_game_manager_aborts_timed_out_startup(game):
    manager = GameManager(ConnectionManager())
    manager.create_game(game)
    websocket = FakeWebSocket()

    await manager.abort_startup(game, websocket)

    assert not game.is_active
    assert websocket.sent == [{"type": "se", "msg": "Game startup timed out. Please try again."}]
    assert websocket.closed
    assert manager.get_game(game.game_id) is None


@pytest.mark.anyio
async def test_game_session_resumes_without_losing_state(game):
    manager = GameManager(ConnectionManager())
    manager.reconnect_grace_seconds = 0.01
    manager.create_game(game)
    player = game.players[0]
    original_socket = FakeWebSocket()
    player.websocket = original_socket
    original_hand = list(player.hand)

    assert manager.reconnect_seconds_left(player.user_id) == 0.01
    assert manager.schedule_disconnect(player.user_id, original_socket)
    assert 0 < manager.reconnect_seconds_left(player.user_id) <= 0.01
    replacement = FakeWebSocket()
    assert manager.resume_player(game, player, replacement)
    assert manager.reconnect_seconds_left(player.user_id) == 0.01
    await asyncio.sleep(0.02)

    assert player.websocket is replacement
    assert player.hand == original_hand
    assert manager.get_game(game.game_id) is game


@pytest.mark.anyio
async def test_game_disconnect_expiry_removes_regular_player(game):
    manager = GameManager(ConnectionManager())
    manager.reconnect_grace_seconds = 0
    manager.create_game(game)
    player = next(player for player in game.players if player.user_id != game.host_id)
    socket = FakeWebSocket()
    player.websocket = socket

    assert not manager.schedule_disconnect("missing", socket)
    assert manager.schedule_disconnect(player.user_id, socket)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert manager.get_game_by_player_id(player.user_id) is None
    await manager.send_whose_turn(None, "Turn", player.user_id)
