import pytest

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
    assert manager.games == []


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
