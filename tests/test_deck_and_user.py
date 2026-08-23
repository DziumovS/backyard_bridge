from src.deck.models import Card, Deck
from src.user.models import Player
from tests.conftest import FakeWebSocket


def test_card_representation_and_playability():
    current = Card("9", "♠")
    assert str(current) == "9 ♠"
    assert current.card_to_dict() == {"rank": "9", "suit": "♠"}
    assert Card("9", "♥").can_play_on(current)
    assert Card("8", "♠").can_play_on(current)
    assert Card("J", "♦").can_play_on(current)
    assert not Card("8", "♥").can_play_on(current)
    assert Card("8", "♥").can_play_on(current, {"suit": "♥"})
    assert Card("J", "♣").can_play_on(current, {"suit": "♥"})
    assert Card("J", "♣").can_play_on(current, j=True)
    assert not Card("9", "♣").can_play_on(current, j=True)


def test_deck_create_draw_flip_and_empty(monkeypatch):
    monkeypatch.setattr("src.deck.models.shuffle", lambda cards: None)
    deck = Deck()
    assert len(deck) == 36
    assert str(deck) == "Deck has 36 cards left"
    first = deck.draw_card()
    assert first.rank == "A" and first.suit == "♣"

    deck.deck = []
    deck.bounce_deck = [Card("6", "♠"), Card("7", "♥")]
    drawn = deck.draw_card()
    assert drawn.rank == "7"
    assert deck.scores_rate == 2
    assert deck.bounce_deck == []

    deck.deck = []
    deck.bounce_deck = []
    assert deck.is_decks_empty()
    deck.bounce_deck = [Card("8", "♣")]
    assert deck.is_decks_empty_for_eight(Card("8", "♦"))
    assert not deck.is_decks_empty_for_eight(Card("7", "♦"))


def test_deck_helpers(monkeypatch):
    deck = Deck()
    previous_len = len(deck)
    monkeypatch.setattr("src.deck.models.choice", lambda values: values[0])
    deck.add_to_deck_random_card()
    assert len(deck) == previous_len + 1
    assert deck.deck[-1].card_to_dict() == {"rank": "6", "suit": "♠"}
    deck.insert_to_bounce_deck(None)
    deck.insert_to_bounce_deck(Card("Q", "♥"))
    assert deck.bounce_deck[0].rank == "Q"


def test_player_hand_options_and_winner(monkeypatch):
    player = Player("id", FakeWebSocket(), "Name")
    player.hand = [Card("9", "♠"), Card("J", "♥"), Card("8", "♦")]
    assert player.dict_to_card({"rank": "J", "suit": "♥"}) is player.hand[1]
    assert player.dict_to_card({"rank": "A", "suit": "♣"}) is None
    assert player.hand_to_dict()[0] == {"rank": "9", "suit": "♠"}
    assert len(player.get_playable_cards(Card("9", "♣"))) == 2
    assert player.get_playable_cards(Card("9", "♣"), to_dict=True)[0]["rank"] == "9"

    player.options.must_draw = 2
    assert player.options_to_dict()["must_draw"] == 2
    player.set_default_options(can_draw=False)
    assert not player.options.can_draw

    player.hand = []
    assert player.has_won(Card("9", "♠"))
    assert not player.has_won(Card("6", "♠"))
    player.scores = 10
    player.reset_score()
    player.reset_hand()
    assert player.scores == 0 and player.hand == []


def test_prepare_playable_cards(game):
    player = game.players[0]
    player.hand = [Card("J", "♠"), Card("9", "♥")]
    game.current_card = Card("8", "♥")
    assert len(player.prepare_playable_cards(game)) == 2
    player.options.must_skip = True
    assert player.prepare_playable_cards(game) == ()
    player.set_default_options()
    assert player.prepare_playable_cards(game, playable_cards=False) == ()
    game.current_card = Card("J", "♦")
    game.chosen_suit = {"suit": "♣", "chooser_id": player.user_id}
    assert player.prepare_playable_cards(game) == [{"rank": "J", "suit": "♠"}]


def test_player_draws_from_deck(monkeypatch):
    monkeypatch.setattr("src.deck.models.shuffle", lambda cards: None)
    deck = Deck()
    player = Player("id", FakeWebSocket(), "Name")
    player.draw_card(deck)
    assert len(player.hand) == 1
