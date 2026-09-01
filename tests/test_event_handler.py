import asyncio

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
async def test_first_turn_ignores_server_only_player(game):
    _, handler = setup_manager(game)
    game.get_current_player().websocket = None
    await handler.send_first_turn(game)


@pytest.mark.anyio
async def test_play_normal_card_broadcasts_state(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    previous = Card("9", "♠")
    played = Card("9", "♥")
    current.hand = [played, Card("Q", "♥")]
    game.current_card = previous
    game.last_cards_j[current.user_id] = 1

    await handler.handle_played_card(played.card_to_dict(), None, game)

    assert game.current_card is played
    assert played not in current.hand
    assert game.deck.bounce_deck[0] is previous
    assert all(player.websocket.sent[-1]["type"] == "gd" for player in game.players)
    assert game.last_cards_j[current.user_id] == 1


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
@pytest.mark.parametrize("played", [Card("Q", "♠"), Card("8", "♠")])
async def test_existing_round_reason_is_not_overwritten(game, played):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    current.hand = [played] if played.rank == "Q" else [played, Card("Q", "♠")]
    game.current_card = Card("9", "♠")
    game.why_end = "bridge"
    if played.rank == "8":
        game.deck.deck = []
        game.deck.bounce_deck = []

    await handler.handle_played_card(played.card_to_dict(), None, game)

    assert game.why_end == "bridge"


@pytest.mark.anyio
async def test_bridge_prompt_is_safe_for_a_server_only_player(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    current.websocket = None
    jack = Card("J", "♥")
    current.hand = [jack, Card("J", "♦")]
    game.current_card = Card("9", "♠")
    game.four_of_a_kind_tracker.current_rank = "J"
    game.four_of_a_kind_tracker.count = 3

    await handler.handle_played_card(jack.card_to_dict(), "♣", game)

    assert game.bridge_pending_for == current.user_id


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
        (1, False, True, (0, False, True, False)),
        (1, True, True, (0, True, False, False)),
        (0, True, True, (0, False, True, False)),
        (0, False, True, (0, True, True, False)),
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

    assert (
        current.options.must_draw,
        current.options.must_skip,
        current.options.can_draw,
        current.options.can_skip,
    ) == expected


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
async def test_scores_rate_change_is_announced_only_when_discard_pile_flips(game):
    _, handler = setup_manager(game)
    current = game.get_current_player()
    game.current_card = Card("8", "♠")
    game.deck.deck = [Card("9", "♣")]
    game.deck.bounce_deck = [Card("Q", "♥"), Card("K", "♦")]
    current.options.must_draw = 2
    current.options.must_skip = True
    current.options.can_draw = False

    await handler.handle_drew_card(game, current.user_id)
    assert game.deck.scores_rate == 1
    assert all(player.websocket.sent[-1]["scores_rate_changed"] is False for player in game.players)

    await handler.handle_drew_card(game, current.user_id)
    assert game.deck.scores_rate == 2
    assert all(player.websocket.sent[-1]["scores_rate_changed"] is True for player in game.players)

    await handler.handle_skip_turn(game, current.user_id)
    assert all(player.websocket.sent[-1]["scores_rate_changed"] is False for player in game.players)

    next_player = game.get_current_player()
    await handler.handle_drew_card(game, next_player.user_id)
    assert game.deck.scores_rate == 2
    assert all(player.websocket.sent[-1]["scores_rate_changed"] is False for player in game.players)


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
async def test_skip_turn_with_empty_deck_continues_when_a_card_is_playable(game):
    _, handler = setup_manager(game)
    game.current_card = Card("9", "♠")
    game.get_next_player().hand = [Card("Q", "♠")]
    game.deck.deck = []
    game.deck.bounce_deck = []
    game.get_current_player().options.can_skip = True

    await handler.handle_skip_turn(game)

    assert game.why_end is None
    assert not game.get_current_player().options.can_draw


@pytest.mark.anyio
async def test_skip_turn_preserves_an_existing_empty_deck_reason(game):
    _, handler = setup_manager(game)
    game.current_card = Card("9", "♠")
    game.get_next_player().hand = [Card("Q", "♥")]
    game.deck.deck = []
    game.deck.bounce_deck = []
    game.why_end = "bridge"
    game.get_current_player().options.can_skip = True

    await handler.handle_skip_turn(game)

    assert game.why_end == "bridge"


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
async def test_disconnect_player_returns_hand_transfers_effects_and_closes_game(game, monkeypatch):
    manager, handler = setup_manager(game)
    third = Player("third", FakeWebSocket(), "Third")
    third.hand = [Card("9", "♥")]
    manager.add_player(game, third)
    leaving = next(player for player in game.players if player.user_id != game.host_id)
    game.current_player_index = game.players.index(leaving)
    returned_card = Card("Q", "♠")
    leaving.hand = [returned_card]
    leaving.options.must_draw = 2
    leaving.options.must_skip = True
    game.opening_turn_pending = False
    recipient = game.get_next_player()
    initial_deck_size = len(game.deck.deck)
    shuffled = []
    monkeypatch.setattr("src.game.handlers.shuffle", lambda cards: shuffled.append(list(cards)))

    await handler.handle_disconnect_game(leaving.user_id, error=True)
    assert leaving not in game.players
    assert not leaving.websocket.closed
    assert leaving.hand == []
    assert len(game.deck.deck) == initial_deck_size - 1
    assert returned_card in recipient.hand
    assert shuffled and returned_card in shuffled[0]
    assert recipient.options.must_draw == 0
    assert not recipient.options.must_skip
    assert game.get_current_player() is not recipient
    assert recipient.options.can_draw
    assert not recipient.options.can_skip
    assert game.game_id in manager.games

    await handler.handle_disconnect_game(third.user_id)
    assert not game.is_active
    assert game.game_id not in manager.games
    assert game.players[0].websocket.closed


@pytest.mark.anyio
async def test_host_disconnect_ends_game(game):
    manager, handler = setup_manager(game)
    host = game.get_player_or_none(game.host_id)

    await handler.handle_disconnect_game(host.user_id, error=True)

    assert not game.is_active
    assert manager.get_game(game.game_id) is None
    for player in game.players:
        if player is not host:
            assert player.websocket.sent[-1]["type"] == "nep"


@pytest.mark.anyio
async def test_explicit_host_leave_uses_immediate_leave_message(game):
    manager, handler = setup_manager(game)
    host = game.get_player_or_none(game.host_id)
    guest = next(player for player in game.players if player is not host)

    await handler.handle_disconnect_game(host.user_id)

    assert manager.get_game(game.game_id) is None
    assert guest.websocket.sent[-1] == {
        "type": "nep",
        "msg": "The host left the game, so you were returned to the home page",
    }


@pytest.mark.anyio
async def test_disconnect_unknown_player_is_noop(game):
    _, handler = setup_manager(game)
    await handler.handle_disconnect_game("missing")


@pytest.mark.anyio
async def test_disconnect_stale_player_mapping_is_noop(game):
    manager, handler = setup_manager(game)
    manager._game_ids_by_player["ghost"] = game.game_id

    await handler.handle_disconnect_game("ghost")

    assert manager.get_game(game.game_id) is game


@pytest.mark.anyio
@pytest.mark.parametrize("player_count", [2, 3, 4])
async def test_all_players_can_disconnect_concurrently(game, players, player_count):
    manager, handler = setup_manager(game)
    for player in players[2:player_count]:
        manager.add_player(game, player)

    await asyncio.gather(*(
        handler.handle_disconnect_game(player.user_id, error=True)
        for player in list(game.players)
    ))

    assert manager.get_game(game.game_id) is None
    assert all(manager.get_game_by_player_id(player.user_id) is None for player in players[:player_count])
