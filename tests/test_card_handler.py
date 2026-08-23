import pytest

from src.deck.models import Card


def configure_play(game, rank, remaining=None):
    player = game.get_current_player()
    previous = Card("9", "♣")
    played = Card(rank, "♠")
    player.hand = [played] + list(remaining or [])
    game.current_card = played
    return player, previous, played


def test_handle_six_with_and_without_playable_cards(game):
    player, previous, _ = configure_play(game, "6", [Card("6", "♥")])
    game.card_handler.handle_special_cards(player, previous)
    assert not player.options.can_skip
    assert player.options.can_draw

    player, _, _ = configure_play(game, "6", [Card("9", "♥")])
    player.hand = [Card("9", "♥")]
    game.card_handler.handle_card_six(player)
    assert player.options.must_draw == 1

    game.deck.deck = []
    game.deck.bounce_deck = []
    player.options.must_draw = 2
    game.card_handler.handle_card_six(player)
    assert player.options.must_draw == 0


@pytest.mark.parametrize(
    ("rank", "draw", "current_skip", "next_skip"),
    [
        ("7", 1, True, False),
        ("8", 2, True, True),
        ("A", 0, True, True),
        ("Q", 0, True, False),
    ],
)
def test_special_and_normal_cards(game, rank, draw, current_skip, next_skip):
    player, previous, _ = configure_play(game, rank, [Card("9", "♥")])
    next_player = game.get_next_player()
    game.card_handler.handle_special_cards(player, previous)
    assert player.options.must_skip is current_skip
    assert next_player.options.must_draw == draw
    assert next_player.options.must_skip is next_skip


def test_jack_options_and_tracking(game):
    player, previous, _ = configure_play(game, "J", [Card("J", "♥"), Card("9", "♦")])
    game.card_handler.handle_special_cards(player, previous)
    assert not player.options.can_draw and player.options.can_skip
    assert not player.options.must_skip
    assert game.last_cards_j[player.user_id] == 1

    previous = game.current_card
    game.current_card = player.hand[0]
    game.card_handler.handle_special_cards(player, previous)
    assert player.options.must_skip
    assert game.last_cards_j[player.user_id] == 2
