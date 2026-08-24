import asyncio
from html import escape

import pytest
from pydantic import ValidationError

from src.connection.manager import ConnectionManager
from src.deck.models import Card
from src.game.errors import InvalidAction
from src.game.manager import GameManager
from src.game.router import websocket_game
from src.lobby.manager import LobbyManager
from src.lobby.models import Lobby
from src.lobby.router import game_manager
from src.protocol import game_auth_adapter, game_message_adapter, lobby_message_adapter
from src.user.models import User
from tests.conftest import FakeWebSocket


def setup_game(game):
    manager = GameManager(ConnectionManager())
    manager.create_game(game)
    for player in game.players:
        player.websocket = FakeWebSocket()
    return manager, manager.event_handler


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "crl", "user_name": ""},
        {"type": "crl", "user_name": "x" * 14},
        {"type": "jl", "user_name": "Name", "lobby_id": "wrong"},
        {"type": "sg", "extra": True},
        {"type": "unknown"},
    ],
)
def test_lobby_protocol_rejects_invalid_messages(payload):
    with pytest.raises(ValidationError):
        lobby_message_adapter.validate_python(payload)


def test_protocol_strips_names_and_validates_cards():
    message = lobby_message_adapter.validate_python({"type": "crl", "user_name": "  Name  "})
    assert message.user_name == "Name"
    assert lobby_message_adapter.validate_python({"type": "ab"}).type == "ab"
    kick = lobby_message_adapter.validate_python({"type": "ku", "user_id": "player-1"})
    assert kick.user_id == "player-1"
    with pytest.raises(ValidationError):
        lobby_message_adapter.validate_python({"type": "ku", "user_id": ""})
    valid = game_message_adapter.validate_python(
        {"type": "pc", "card": {"rank": "J", "suit": "♥"}, "chosen_suit": "♣"}
    )
    assert valid.card.rank == "J"
    with pytest.raises(ValidationError):
        game_message_adapter.validate_python(
            {"type": "pc", "card": {"rank": "1", "suit": "x"}, "chosen_suit": None}
        )
    with pytest.raises(ValidationError):
        game_message_adapter.validate_python({"type": "dc", "card": {}})
    assert game_auth_adapter.validate_python({"type": "auth", "token": "x" * 32}).token == "x" * 32
    with pytest.raises(ValidationError):
        game_auth_adapter.validate_python({"type": "auth", "token": "short"})


@pytest.mark.anyio
async def test_lobby_rejects_full_ingame_and_duplicate_users(users):
    manager = LobbyManager(ConnectionManager())
    lobby = Lobby("abcdef", users[0])
    for user in users[1:]:
        lobby.add_user(user)
    manager.add_lobby(lobby)
    extra = User("extra", FakeWebSocket(), "Extra")

    await manager.handlers.handle_join_lobby(extra, extra.websocket, lobby.lobby_id)
    assert extra.websocket.sent[-1]["type"] == "se"

    lobby.remove_user(users[-1].user_id)
    lobby.in_game = True
    await manager.handlers.handle_join_lobby(extra, extra.websocket, lobby.lobby_id)
    assert extra.user_id not in lobby.users

    lobby.in_game = False
    duplicate = User(users[1].user_id, FakeWebSocket(), "Duplicate")
    await manager.handlers.handle_join_lobby(duplicate, duplicate.websocket, lobby.lobby_id)
    assert duplicate.websocket.sent[-1]["msg"] == "This player is already in the lobby."


@pytest.mark.anyio
async def test_only_host_can_start_valid_lobby(users):
    manager = LobbyManager(ConnectionManager())
    lobby = Lobby("abcdef", users[0])
    manager.add_lobby(lobby)
    assert await manager.handlers.handle_start_game(users[0].user_id) is None
    manager.add_user(lobby, users[1])
    assert await manager.handlers.handle_start_game(users[1].user_id) is None
    result = await manager.handlers.handle_start_game(users[0].user_id)
    assert result[0] == lobby.lobby_id
    assert lobby.in_game
    assert await manager.handlers.handle_start_game(users[0].user_id) is None


@pytest.mark.anyio
async def test_game_websocket_rejects_missing_wrong_and_duplicate_session(game):
    game_manager.clear()
    game_manager.create_game(game)
    player = game.players[0]

    malformed = FakeWebSocket([{"type": "auth", "token": "short"}])
    await websocket_game(malformed, game.game_id, player.user_id)
    assert malformed.closed and malformed.close_code == 1008

    missing = FakeWebSocket([{"type": "auth", "token": player.session_token}])
    await websocket_game(missing, "missing", player.user_id)
    assert missing.closed and missing.close_code == 1008

    wrong = FakeWebSocket([{"type": "auth", "token": "x" * 32}])
    await websocket_game(wrong, game.game_id, player.user_id)
    assert wrong.sent[-1]["msg"] == "Invalid game session."

    player.websocket = FakeWebSocket()
    duplicate = FakeWebSocket([{"type": "auth", "token": player.session_token}])
    await websocket_game(duplicate, game.game_id, player.user_id)
    assert duplicate.sent[-1]["msg"] == "This player is already connected."
    game_manager.clear()


@pytest.mark.anyio
async def test_non_current_player_cannot_control_turn(game):
    _, handler = setup_game(game)
    current = game.get_current_player()
    attacker = game.get_next_player()
    current.hand = [Card("9", "♠"), Card("Q", "♥")]
    game.current_card = Card("9", "♥")

    calls = [
        handler.handle_played_card(current.hand[0].card_to_dict(), None, game, attacker.user_id),
        handler.handle_drew_card(game, attacker.user_id),
        handler.handle_skip_turn(game, attacker.user_id),
        handler.handle_game_over(game, attacker.user_id),
    ]
    for call in calls:
        with pytest.raises(InvalidAction, match="not your turn"):
            await call


@pytest.mark.anyio
async def test_server_validates_card_suit_and_options(game):
    _, handler = setup_game(game)
    current = game.get_current_player()
    game.current_card = Card("9", "♠")
    current.hand = [Card("Q", "♥"), Card("J", "♦"), Card("9", "♥")]

    with pytest.raises(InvalidAction, match="not in your hand"):
        await handler.handle_played_card({"rank": "A", "suit": "♣"}, None, game, current.user_id)
    with pytest.raises(InvalidAction, match="cannot be played"):
        await handler.handle_played_card(current.hand[0].card_to_dict(), None, game, current.user_id)
    with pytest.raises(InvalidAction, match="Choose a suit"):
        await handler.handle_played_card(current.hand[1].card_to_dict(), None, game, current.user_id)
    with pytest.raises(InvalidAction, match="only be chosen"):
        await handler.handle_played_card(current.hand[2].card_to_dict(), "♣", game, current.user_id)

    current.options.must_draw = 1
    with pytest.raises(InvalidAction, match="required action"):
        await handler.handle_played_card(current.hand[2].card_to_dict(), None, game, current.user_id)


@pytest.mark.anyio
async def test_server_rejects_invalid_draw_skip_bridge_and_reset(game):
    _, handler = setup_game(game)
    current = game.get_current_player()
    current.options.can_draw = False
    with pytest.raises(InvalidAction, match="cannot draw"):
        await handler.handle_drew_card(game, current.user_id)
    with pytest.raises(InvalidAction, match="cannot skip"):
        await handler.handle_skip_turn(game, current.user_id)
    with pytest.raises(InvalidAction, match="Bridge"):
        await handler.handle_game_over(game, current.user_id)
    with pytest.raises(InvalidAction, match="not over"):
        await handler.handle_reset_game(game, game.host_id)
    with pytest.raises(InvalidAction, match="Only the host"):
        await handler.handle_reset_game(game, game.get_next_player().user_id)


@pytest.mark.anyio
async def test_empty_deck_and_finished_round_reject_actions(game):
    _, handler = setup_game(game)
    current = game.get_current_player()
    game.deck.deck = []
    game.deck.bounce_deck = []
    with pytest.raises(InvalidAction, match="no cards"):
        await handler.handle_drew_card(game, current.user_id)
    game.round_over = True
    with pytest.raises(InvalidAction, match="already over"):
        await handler.handle_drew_card(game, current.user_id)


@pytest.mark.anyio
async def test_bridge_and_scoring_are_idempotent(game):
    _, handler = setup_game(game)
    current = game.get_current_player()
    game.bridge_pending_for = current.user_id
    await handler.handle_game_over(game, current.user_id)
    scores = [player.scores for player in game.players]
    with pytest.raises(InvalidAction, match="already over"):
        await handler.handle_game_over(game, current.user_id)
    assert [player.scores for player in game.players] == scores


def test_user_generated_html_is_escaped(game):
    payload = '<img src=x onerror="alert(1)">'
    game.players[0].user_name = payload
    game.players[0].scores = 126
    message, results = game.get_game_over_message(game.players[0])
    assert payload not in message + results
    assert escape(payload) in message + results


@pytest.mark.anyio
async def test_game_action_lock_serializes_mutations(game):
    order = []

    async def mutate(value):
        async with game.action_lock:
            order.append(f"start-{value}")
            await asyncio.sleep(0)
            order.append(f"end-{value}")

    await asyncio.gather(mutate(1), mutate(2))
    assert order == ["start-1", "end-1", "start-2", "end-2"]
