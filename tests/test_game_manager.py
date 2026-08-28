import pytest
import asyncio

from src.connection.manager import ConnectionManager
from src.deck.models import Card
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
    player.scores = -20
    game.players[1].scores = -15
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
    assert {
        current["user_id"]: current["scores"] for current in state["players"]
    } == {
        player.user_id: -20,
        game.players[1].user_id: -15,
    }

    await manager.send_game_data(player, True, game, scores_rate_changed=True)
    assert player.websocket.sent[-1]["scores_rate_changed"] is True


def setup_automatic_actions(game):
    manager = GameManager(ConnectionManager())
    manager.bot_controller.action_delay = 0
    manager.create_game(game)
    for player in game.players:
        player.websocket = FakeWebSocket()
        player.set_default_options()
    return manager


@pytest.mark.anyio
async def test_normal_card_finishes_the_turn_automatically(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    next_player = game.get_next_player()
    played = Card("9", "♥")
    current.hand = [played, Card("Q", "♥")]
    next_player.hand = [Card("K", "♥")]
    game.current_card = Card("9", "♠")

    await manager.event_handler.handle_played_card(played.card_to_dict(), None, game, current.user_id)
    assert current.options.must_skip
    await manager.run_automatic_actions(game)

    assert game.get_current_player() is next_player
    assert not current.options.must_skip


@pytest.mark.anyio
async def test_seven_forces_the_next_player_to_draw_automatically(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    next_player = game.get_next_player()
    played = Card("7", "♠")
    current.hand = [played, Card("Q", "♠")]
    next_player.hand = [Card("Q", "♦")]
    game.current_card = Card("9", "♠")
    game.deck.deck = [Card("K", "♣")]
    game.deck.bounce_deck = []

    await manager.event_handler.handle_played_card(played.card_to_dict(), None, game, current.user_id)
    await manager.run_automatic_actions(game)

    assert game.get_current_player() is current
    assert len(next_player.hand) == 2
    assert not next_player.options.must_draw
    assert not next_player.options.must_skip
    assert any(message["type"] == "adc" for message in next_player.websocket.sent)


@pytest.mark.anyio
async def test_ace_skips_both_required_turns_automatically(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    skipped_player = game.get_next_player()
    played = Card("A", "♠")
    current.hand = [played, Card("Q", "♠")]
    game.current_card = Card("9", "♠")

    await manager.event_handler.handle_played_card(played.card_to_dict(), None, game, current.user_id)
    await manager.run_automatic_actions(game)

    assert game.get_current_player() is current
    assert not current.options.must_skip
    assert not skipped_player.options.must_skip


@pytest.mark.anyio
async def test_eight_draws_two_and_skips_the_penalized_player(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    penalized_player = game.get_next_player()
    played = Card("8", "♠")
    current.hand = [played, Card("Q", "♥")]
    penalized_player.hand = [Card("9", "♥")]
    game.current_card = Card("9", "♠")
    game.deck.deck = [Card("Q", "♣"), Card("K", "♦")]
    game.deck.bounce_deck = []

    await manager.event_handler.handle_played_card(played.card_to_dict(), None, game, current.user_id)
    await manager.run_automatic_actions(game)

    assert game.get_current_player() is current
    assert len(penalized_player.hand) == 3
    assert penalized_player.options.must_draw == 0
    assert not penalized_player.options.must_skip


@pytest.mark.anyio
async def test_eight_returns_to_blocked_player_and_draws_across_rounds(game):
    manager = setup_automatic_actions(game)
    human = game.get_current_player()
    bot = game.get_next_player()
    bot.is_bot = True

    for _ in range(4):
        game.reset_game()
        game.current_player_index = game.players.index(human)
        human.websocket.sent.clear()
        bot.websocket.sent.clear()

        eight = Card("8", "♠")
        blocked_card = Card("Q", "♥")
        matching_draw = Card("K", "♠")
        human.hand = [eight, blocked_card]
        bot.hand = [Card("9", "♥")]
        game.current_card = Card("9", "♠")
        game.deck.deck = [matching_draw, Card("Q", "♣"), Card("K", "♦")]
        game.deck.bounce_deck = []

        await manager.event_handler.handle_played_card(
            eight.card_to_dict(),
            None,
            game,
            human.user_id,
        )
        await manager.run_automatic_actions(game)

        assert game.get_current_player() is human
        assert human.hand == [blocked_card, matching_draw]
        assert not human.options.can_draw
        assert human.options.can_skip
        assert human.get_playable_cards(game.current_card) == [matching_draw]
        assert any(
            message == {"type": "adc", "current_player": human.user_id}
            for message in human.websocket.sent
        )
        assert any(
            message["type"] == "wt" and message["current_player"] == human.user_id
            for message in human.websocket.sent
        )
        automatic_only_states = [
            message
            for message in human.websocket.sent
            if (
            message["type"] == "gd"
            and message["current_player"] is True
            and message["player_options"] == {
                "must_draw": 0,
                "must_skip": False,
                "can_draw": True,
                "can_skip": False,
            }
            and not message["playable_cards"]
            )
        ]
        assert automatic_only_states
        assert all(message["automatic_action_pending"] for message in automatic_only_states)
        final_state = next(
            message for message in reversed(human.websocket.sent) if message["type"] == "gd"
        )
        assert final_state["automatic_action_pending"] is False


@pytest.mark.anyio
async def test_human_only_action_does_not_wait_for_the_bot_delay(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    blocked_card = Card("Q", "♥")
    matching_draw = Card("K", "♠")
    current.hand = [blocked_card]
    game.current_card = Card("9", "♠")
    game.deck.deck = [matching_draw]
    game.deck.bounce_deck = []
    manager.bot_controller.action_delay = 60

    await asyncio.wait_for(manager.run_automatic_actions(game), timeout=0.1)

    assert current.hand == [blocked_card, matching_draw]
    assert current.options.can_skip


@pytest.mark.anyio
async def test_six_draws_only_until_a_choice_becomes_available(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    played = Card("6", "♠")
    blocked_card = Card("Q", "♥")
    first_draw = Card("Q", "♣")
    playable_draw = Card("6", "♦")
    current.hand = [played, blocked_card]
    game.current_card = Card("9", "♠")
    game.deck.deck = [playable_draw, first_draw]
    game.deck.bounce_deck = []

    await manager.event_handler.handle_played_card(played.card_to_dict(), None, game, current.user_id)
    await manager.run_automatic_actions(game)

    assert game.get_current_player() is current
    assert current.hand == [blocked_card, first_draw, playable_draw]
    assert current.options.must_draw == 0
    assert current.options.can_draw
    assert current.get_playable_cards(game.current_card) == [playable_draw]


@pytest.mark.anyio
async def test_six_and_multiple_jacks_preserve_player_choice(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    six = Card("6", "♠")
    remaining_six = Card("6", "♥")
    current.hand = [six, remaining_six]
    game.current_card = Card("9", "♠")

    await manager.event_handler.handle_played_card(six.card_to_dict(), None, game, current.user_id)
    await manager.run_automatic_actions(game)
    assert game.get_current_player() is current
    assert current.hand == [remaining_six]
    assert current.options.can_draw
    assert current.get_playable_cards(game.current_card) == [remaining_six]

    first_jack = Card("J", "♠")
    other_jacks = [Card("J", "♥"), Card("J", "♦")]
    current.hand = [first_jack, *other_jacks]
    current.set_default_options()
    game.current_card = Card("9", "♠")
    await manager.event_handler.handle_played_card(first_jack.card_to_dict(), "♣", game, current.user_id)
    await manager.run_automatic_actions(game)

    assert game.get_current_player() is current
    assert current.hand == other_jacks
    assert current.options.can_skip
    assert not current.options.must_skip


@pytest.mark.anyio
async def test_jack_suit_with_no_matching_card_draws_automatically(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    next_player = game.get_next_player()
    jack = Card("J", "♠")
    blocked_card = Card("Q", "♣")
    matching_draw = Card("K", "♥")
    current.hand = [jack, Card("9", "♦")]
    next_player.hand = [blocked_card]
    game.current_card = Card("9", "♠")
    game.deck.deck = [matching_draw]
    game.deck.bounce_deck = []

    await manager.event_handler.handle_played_card(
        jack.card_to_dict(),
        "♥",
        game,
        current.user_id,
    )
    await manager.run_automatic_actions(game)

    assert game.get_current_player() is next_player
    assert next_player.hand == [blocked_card, matching_draw]
    assert not next_player.options.can_draw
    assert next_player.options.can_skip
    assert next_player.get_playable_cards(game.current_card, game.chosen_suit) == [matching_draw]
    assert any(message["type"] == "adc" for message in next_player.websocket.sent)


@pytest.mark.anyio
async def test_bot_normal_card_with_no_human_response_draws_automatically(game):
    manager = setup_automatic_actions(game)
    bot = game.get_current_player()
    human = game.get_next_player()
    bot.is_bot = True
    played = Card("9", "♥")
    blocked_card = Card("Q", "♣")
    matching_draw = Card("K", "♥")
    bot.hand = [played, Card("Q", "♥")]
    human.hand = [blocked_card]
    game.current_card = Card("9", "♠")
    game.deck.deck = [matching_draw]
    game.deck.bounce_deck = []

    await manager.event_handler.handle_played_card(
        played.card_to_dict(),
        None,
        game,
        bot.user_id,
    )
    await manager.run_automatic_actions(game)

    assert game.get_current_player() is human
    assert human.hand == [blocked_card, matching_draw]
    assert not human.options.can_draw
    assert human.options.can_skip
    assert human.get_playable_cards(game.current_card) == [matching_draw]
    assert any(message["type"] == "adc" for message in human.websocket.sent)


@pytest.mark.anyio
async def test_regular_playable_card_preserves_draw_or_play_choice(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    playable = Card("Q", "♠")
    current.hand = [playable]
    game.current_card = Card("9", "♠")
    original_deck_size = len(game.deck)

    await manager.run_automatic_actions(game)

    assert game.get_current_player() is current
    assert current.hand == [playable]
    assert current.options.can_draw
    assert not current.options.can_skip
    assert len(game.deck) == original_deck_size


@pytest.mark.anyio
async def test_seven_matching_draw_preserves_play_or_skip_choice(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    next_player = game.get_next_player()
    seven = Card("7", "♠")
    blocked_card = Card("Q", "♦")
    matching_draw = Card("K", "♠")
    current.hand = [seven, Card("Q", "♠")]
    next_player.hand = [blocked_card]
    game.current_card = Card("9", "♠")
    game.deck.deck = [matching_draw]
    game.deck.bounce_deck = []

    await manager.event_handler.handle_played_card(
        seven.card_to_dict(),
        None,
        game,
        current.user_id,
    )
    await manager.run_automatic_actions(game)

    assert game.get_current_player() is next_player
    assert next_player.hand == [blocked_card, matching_draw]
    assert not next_player.options.can_draw
    assert next_player.options.can_skip
    assert next_player.get_playable_cards(game.current_card) == [matching_draw]


@pytest.mark.anyio
async def test_bridge_prompt_prevents_automatic_skip(game):
    manager = setup_automatic_actions(game)
    current = game.get_current_player()
    current.options.must_skip = True
    game.bridge_pending_for = current.user_id

    await manager.run_automatic_actions(game)

    assert game.get_current_player() is current
    assert current.options.must_skip


@pytest.mark.anyio
async def test_game_manager_aborts_timed_out_startup(game):
    manager = GameManager(ConnectionManager())
    manager.create_game(game)
    websocket = FakeWebSocket()

    await manager.abort_startup(game, websocket)

    assert not game.is_active
    assert websocket.sent == [{"type": "se", "msg": "Game startup timed out. Try again."}]
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
