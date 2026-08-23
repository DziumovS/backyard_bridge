import pytest

from src.connection.manager import ConnectionManager
from src.deck.models import Card
from src.game.manager import GameManager
from src.user.models import Player
from tests.conftest import FakeWebSocket


def setup_manager(game):
    manager = GameManager(ConnectionManager())
    manager.create_game(game)
    for player in game.players:
        player.websocket = FakeWebSocket()
    return manager, manager.event_handler


@pytest.mark.anyio
async def test_game_started_for_current_and_other_player(game):
    manager, handler = setup_manager(game)
    current, other = game.players
    await handler.handle_game_started(current.user_id, game)
    await handler.handle_game_started(other.user_id, game)

    assert [message["type"] for message in current.websocket.sent] == ["wt", "gd", "ft"]
    assert [message["type"] for message in other.websocket.sent] == ["wt", "gd"]
    assert game.four_of_a_kind_tracker.current_rank == game.current_card.rank


@pytest.mark.anyio
async def test_play_normal_card_broadcasts_state(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    previous = Card("9", "♠")
    played = Card("9", "♥")
    current.hand = [played, Card("Q", "♥")]
    game.current_card = previous

    await handler.handle_played_card(played.card_to_dict(), None, game)

    assert game.current_card is played
    assert played not in current.hand
    assert game.deck.bounce_deck[0] is previous
    assert all(player.websocket.sent[-1]["type"] == "gd" for player in game.players)


@pytest.mark.anyio
async def test_play_jack_sets_suit_and_prompts_bridge(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    previous = Card("9", "♠")
    jack = Card("J", "♥")
    current.hand = [jack, Card("J", "♦")]
    game.current_card = previous
    game.four_of_a_kind_tracker.current_rank = "J"
    game.four_of_a_kind_tracker.count = 3

    await handler.handle_played_card(jack.card_to_dict(), "♣", game)

    assert game.chosen_suit == {"suit": "♣", "color": "black", "chooser_id": current.user_id}
    assert any(message["type"] == "iib" for message in current.websocket.sent)


@pytest.mark.anyio
async def test_playing_last_card_finishes_round(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    played = Card("Q", "♠")
    current.hand = [played]
    game.current_card = Card("9", "♠")

    await handler.handle_played_card(played.card_to_dict(), None, game)

    assert game.why_end == "empty_hand"
    assert any(message["type"] == "go" for message in current.websocket.sent)


@pytest.mark.anyio
async def test_playing_eight_with_empty_deck_finishes_round(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    played = Card("8", "♠")
    current.hand = [played, Card("Q", "♠")]
    game.current_card = Card("9", "♠")
    game.deck.deck = []
    game.deck.bounce_deck = []

    await handler.handle_played_card(played.card_to_dict(), None, game)

    assert game.why_end == "empty_deck"


@pytest.mark.anyio
async def test_game_over_penalty_draw_then_scores(game, monkeypatch):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    next_player = game.get_next_player()
    next_player.options.must_draw = 1
    game.deck.deck = []
    game.deck.bounce_deck = []
    monkeypatch.setattr("src.deck.models.choice", lambda values: values[0])

    await handler._handle_game_over(current, next_player, game)
    assert len(next_player.hand) == 6
    assert next_player.options.must_draw == 0
    assert next_player.websocket.sent[-1]["type"] == "go"
    assert all(any(message["type"] == "go" for message in player.websocket.sent) for player in game.players)
    scores = [player.scores for player in game.players]
    await handler._handle_game_over(current, next_player, game)
    assert [player.scores for player in game.players] == scores


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("must_draw", "must_skip", "can_draw", "expected"),
    [
        (1, False, True, (0, False, True)),
        (0, True, True, (0, False, True)),
        (0, False, True, (0, True, True)),
    ],
)
async def test_draw_card_option_transitions(game, must_draw, must_skip, can_draw, expected):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    game.current_card = Card("9", "♠")
    current.hand = [Card("Q", "♥")]
    current.options.must_draw = must_draw
    current.options.must_skip = must_skip
    current.options.can_draw = can_draw

    await handler.handle_drew_card(game)

    assert (current.options.must_draw, current.options.must_skip, current.options.can_draw) == expected


@pytest.mark.anyio
async def test_draw_card_on_six_and_reset_draw_skip_options(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    game.current_card = Card("6", "♠")
    current.hand = [Card("6", "♥")]
    current.options.must_draw = 1

    await handler.handle_drew_card(game)

    assert current.options.can_draw


@pytest.mark.anyio
async def test_optional_draw_with_playable_card_allows_skip(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    next_player = game.get_next_player()
    game.current_card = Card("Q", "♠")
    current.hand = [Card("J", "♥")]
    game.deck.deck = [Card("8", "♣"), Card("9", "♦")]
    current.options.can_draw = True

    await handler.handle_drew_card(game)

    assert not current.options.can_draw
    assert current.options.can_skip
    assert current.get_playable_cards(game.current_card) == current.hand[:1]

    await handler.handle_skip_turn(game, current.user_id)

    assert game.get_current_player() is next_player
    assert current.options.can_draw
    assert not current.options.can_skip


@pytest.mark.anyio
async def test_skip_turn_updates_suit_and_broadcasts(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    current.options.must_skip = True
    game.last_cards_j[current.user_id] = 1
    game.chosen_suit = {"suit": "♥", "chooser_id": current.user_id}
    game.current_card = Card("J", "♠")

    await handler.handle_skip_turn(game)

    assert game.get_current_player() is game.players[1]
    assert game.chosen_suit["chooser_id"] is None
    assert all(any(message["type"] == "wt" for message in player.websocket.sent) for player in game.players)


@pytest.mark.anyio
async def test_skip_turn_with_empty_deck_ends_when_no_cards_playable(game):
    _, handler = setup_manager(game)
    game.current_card = Card("9", "♠")
    game.get_next_player().hand = [Card("Q", "♥")]
    game.deck.deck = []
    game.deck.bounce_deck = []
    game.get_current_player().options.can_skip = True

    await handler.handle_skip_turn(game)

    assert game.why_end == "empty_deck"


@pytest.mark.anyio
async def test_show_move_broadcasts_play_and_draw_animations(game):
    _, handler = setup_manager(game)
    from src.game.errors import InvalidAction

    with pytest.raises(InvalidAction):
        await handler.handle_show_my_move(game, {"card": {"rank": "9", "suit": "♠"}})


@pytest.mark.anyio
async def test_explicit_game_over_and_reset(game):
    _, handler = setup_manager(game)
    await handler.handle_game_over(game)
    assert game.why_end == "bridge"

    for player in game.players:
        player.websocket.sent.clear()
    await handler.handle_reset_game(game)
    assert all(message["type"] == "gr" for player in game.players for message in player.websocket.sent[:1])
    assert any(message["type"] == "ft" for message in game.get_current_player().websocket.sent)


@pytest.mark.anyio
async def test_disconnect_player_and_close_game(game):
    manager, handler = setup_manager(game)
    third = Player("third", FakeWebSocket(), "Third")
    third.hand = [Card("9", "♥")]
    game.players.append(third)
    leaving = game.get_current_player()
    leaving.hand = [Card("Q", "♠")]

    await handler.handle_disconnect_game(leaving.user_id, error=True)
    assert leaving not in game.players
    assert not leaving.websocket.closed
    assert game.deck.bounce_deck
    assert game in manager.games

    await handler.handle_disconnect_game(third.user_id)
    assert not game.is_active
    assert game not in manager.games
    assert game.players[0].websocket.closed


@pytest.mark.anyio
async def test_disconnect_unknown_player_is_noop(game):
    _, handler = setup_manager(game)
    await handler.handle_disconnect_game("missing")
