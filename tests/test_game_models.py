import asyncio

import pytest

from src.deck.models import Card
from src.game.models import FourOfAKindTracker, Game
from tests.conftest import FakeWebSocket


def test_four_of_a_kind_tracker():
    tracker = FourOfAKindTracker()
    assert not tracker.checking("9")
    assert not tracker.checking("9")
    assert not tracker.checking("9")
    assert tracker.checking("9")
    assert not tracker.checking("9")
    assert not tracker.checking("8")
    tracker.current_rank = "6"
    tracker.count = 3
    assert not tracker.checking("6")
    tracker.reset()
    assert tracker.current_rank is None and tracker.count == 0


@pytest.mark.anyio
async def test_game_connection_readiness(game):
    game.players[0].websocket = None
    game.players[1].websocket = None
    waiter = asyncio.create_task(game.wait_until_all_ready())
    await asyncio.sleep(0)
    assert not waiter.done()
    game.add_player_websocket("missing", FakeWebSocket())
    game.add_player_websocket(game.players[0].user_id, FakeWebSocket())
    assert not waiter.done()
    game.add_player_websocket(game.players[1].user_id, FakeWebSocket())
    await waiter

    ready = asyncio.create_task(game.wait_until_all_clients_ready())
    initialized = asyncio.create_task(game.wait_until_all_clients_initialized())
    assert game.mark_client_ready(game.players[0].user_id)
    assert not game.mark_client_ready(game.players[0].user_id)
    assert not ready.done()
    assert game.mark_client_ready(game.players[1].user_id)
    await ready
    game.mark_client_initialized(game.players[0].user_id)
    assert not initialized.done()
    game.mark_client_initialized(game.players[1].user_id)
    await initialized

    game.all_connected_event.clear()
    game.all_ready_event.clear()
    game.all_initialized_event.clear()
    game.startup_timeout_seconds = 0
    assert not await game.wait_until_all_ready()
    assert not await game.wait_until_all_clients_ready()
    assert not await game.wait_until_all_clients_initialized()


def test_game_player_navigation_and_removal(game):
    first, second = game.players
    assert game.get_player_or_none(first.user_id) is first
    assert game.get_player_or_none("missing") is None
    assert game.is_current_player(first.user_id)
    assert game.get_current_player() is first
    assert game.get_next_player() is second
    assert game.get_players_websocket() == []
    game.next_player()
    assert game.get_current_player() is second
    game.remove_player(first)
    game.remove_player(first)
    assert game.players == [second]


def test_game_removes_played_card_and_tracks_bridge(game):
    player = game.get_current_player()
    player.hand = [Card("9", "♠"), Card("Q", "♥")]
    game.current_card = player.hand[0]
    previous = Card("8", "♣")
    game.remove_played_card(player, previous)
    assert player.hand[0].rank == "Q"
    assert game.deck.bounce_deck[0] is previous

    for _ in range(3):
        assert not game.is_it_bridge(Card("K", "♣"))
    assert game.is_it_bridge(Card("K", "♥"))


def test_game_scoring_and_results(game):
    first, second = game.players
    first.hand = [Card("J", "♠"), Card("J", "♥")]
    second.hand = [Card("10", "♠"), Card("Q", "♥"), Card("A", "♦"), Card("9", "♣")]
    game.last_cards_j[first.user_id] = 2
    scores = game.calculate_scores()
    assert scores == [
        {"player_id": first.user_id, "scores": 0},
        {"player_id": second.user_id, "scores": 35},
    ]

    first.scores = 130
    players_scores, losers, winners = game.get_players_game_results()
    assert len(players_scores) == 2
    assert losers == [{"player": first.user_name, "scores": 130}]
    assert winners == [{"player": second.user_name, "scores": 35}]


def test_score_exactly_125_resets(game):
    first, second = game.players
    first.scores = 115
    first.hand = [Card("10", "♠")]
    second.hand = []
    game.calculate_scores()
    assert first.scores == 0


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("bridge", "called Bridge"),
        ("empty_deck", "empty"),
        ("empty_hand", "played all their cards"),
    ],
)
def test_game_over_messages_without_losers(game, reason, expected):
    game.why_end = reason
    game.players[0].scores = 10
    game.players[1].scores = 20
    message, results = game.get_game_over_message(game.players[0])
    assert expected in message
    assert "Round scores" in results


def test_game_over_messages_with_one_and_multiple_winners(game):
    first, second = game.players
    first.scores = 126
    second.scores = 20
    _, results = game.get_game_over_message(first)
    assert "a player has" in results and "winner" in results

    from src.user.models import Player

    third = Player("3", FakeWebSocket(), "Third")
    third.scores = 30
    game.players.append(third)
    _, results = game.get_game_over_message(first)
    assert "winners" in results

    second.scores = 130
    third.scores = 140
    _, results = game.get_game_over_message(first)
    assert "players have" in results


def test_reset_game_resets_round_state(game, monkeypatch):
    first, second = game.players
    first.scores = 126
    second.scores = 125
    first.hand = []
    game.is_active = False
    game.chosen_suit = {"suit": "♥"}
    game.last_cards_j = {first.user_id: 1}
    game.why_end = "bridge"
    game.four_of_a_kind_tracker.current_rank = "Q"
    game.four_of_a_kind_tracker.count = 3
    game.ready_player_ids.add(first.user_id)
    game.initialized_player_ids.add(first.user_id)
    game.all_ready_event.set()
    game.all_initialized_event.set()

    monkeypatch.setattr("src.deck.models.shuffle", lambda cards: None)
    monkeypatch.setattr("src.game.models.random.shuffle", lambda values: None)
    game.reset_game()

    assert game.is_active
    assert game.current_player_index == 0
    assert game.chosen_suit is None
    assert game.last_cards_j == {}
    assert game.why_end is None
    assert not game.ready_player_ids and not game.initialized_player_ids
    assert not game.all_ready_event.is_set() and not game.all_initialized_event.is_set()
    assert all(player.scores == 0 for player in game.players)
    assert all(len(player.hand) == 5 for player in game.players)
    assert game.current_card in game.players[0].hand


def test_current_card_helpers(game):
    assert game.current_card_to_dict() == game.current_card.card_to_dict()
    assert game.card_distribution() is game.current_card
