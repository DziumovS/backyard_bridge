import pytest
from unittest.mock import AsyncMock

from src.bot.controller import BotController, default_action_delay
from src.bot.factory import BotFactory
from src.bot.models import BotPlayer, BotUser
from src.bot.strategy import BotStrategy
from src.connection.manager import ConnectionManager
from src.deck.models import Card
from src.game.manager import GameManager
from src.game.models import Game
from src.user.models import Player
from tests.conftest import FakeWebSocket


def make_bot_game(monkeypatch):
    monkeypatch.setattr("src.deck.models.shuffle", lambda cards: None)
    monkeypatch.setattr("src.game.models.random.shuffle", lambda players: None)
    bot = BotPlayer("bot-1", "Alex Bot")
    human = Player("human", FakeWebSocket(), "Human")
    game = Game("bot-game", [bot, human], host_id=human.user_id)
    human.websocket = FakeWebSocket()
    manager = GameManager(ConnectionManager())
    manager.bot_controller.action_delay = 0
    manager.create_game(game)
    game.opening_turn_pending = False
    return manager, game, bot, human


def test_bot_factory_creates_unique_server_side_players(monkeypatch):
    monkeypatch.setattr("src.bot.factory.secrets.token_urlsafe", lambda _: "token")
    factory = BotFactory(names=("Alex", "Taylor"), chooser=lambda names: names[0])
    bot = factory.create({"Alex Bot"})

    assert isinstance(bot, BotUser)
    assert bot.user_id == "bot-token"
    assert bot.user_name == "Taylor Bot"
    assert bot.websocket is None
    assert bot.is_bot

    repeated = BotFactory(names=("Alex",), chooser=lambda names: names[0]).create({"Alex Bot"})
    assert repeated.user_name == "Alex Bot"
    player = BotPlayer.from_user(bot)
    assert player.user_id == bot.user_id and player.session_token == bot.session_token


def test_bot_strategy_prioritizes_winning_and_disruptive_cards():
    strategy = BotStrategy()
    player = BotPlayer("bot", "Alex Bot")
    game = type("GameState", (), {})()
    game.current_card = Card("9", "♠")
    game.chosen_suit = None
    game.bridge_pending_for = None

    winning_card = Card("Q", "♠")
    player.hand = [winning_card]
    assert strategy.choose_card(game, player) is winning_card

    ace = Card("A", "♠")
    nine = Card("9", "♥")
    player.hand = [nine, ace, Card("6", "♠")]
    assert strategy.choose_card(game, player) is ace
    assert not strategy.should_call_bridge(game, player)
    game.bridge_pending_for = player.user_id
    assert strategy.should_call_bridge(game, player)


def test_bot_strategy_chains_jacks_and_selects_dominant_suit():
    strategy = BotStrategy()
    player = BotPlayer("bot", "Alex Bot")
    jack = Card("J", "♠")
    player.hand = [jack, Card("J", "♥"), Card("Q", "♦"), Card("9", "♦")]
    game = type("GameState", (), {})()
    game.current_card = Card("J", "♣")
    game.chosen_suit = {"suit": "♠", "chooser_id": player.user_id}

    assert strategy.playable_cards(game, player) == player.hand[:2]
    assert strategy.choose_suit(player, jack) == "♦"

    game.current_card = Card("9", "♣")
    game.chosen_suit = {"suit": "♦", "chooser_id": None}
    assert strategy.playable_cards(game, player) == player.hand


def test_bot_delay_configuration(monkeypatch):
    monkeypatch.setenv("BACKYARD_BRIDGE_BOT_ACTION_DELAY", "-1")
    assert default_action_delay() == 0
    monkeypatch.setenv("BACKYARD_BRIDGE_BOT_ACTION_DELAY", "invalid")
    assert default_action_delay() == 0.45
    monkeypatch.delenv("BACKYARD_BRIDGE_BOT_ACTION_DELAY")
    assert BotController(object()).action_delay == 0.45


@pytest.mark.anyio
async def test_bot_plays_then_completes_its_turn(monkeypatch):
    manager, game, bot, human = make_bot_game(monkeypatch)
    game.current_card = Card("9", "♠")
    played = Card("9", "♥")
    bot.hand = [played, Card("Q", "♥")]

    await manager.run_bot_turns(game)

    assert game.get_current_player() is human
    assert played not in bot.hand
    assert any(message["type"] == "apc" for message in human.websocket.sent)
    assert any(message["type"] == "wt" for message in human.websocket.sent)


@pytest.mark.anyio
async def test_bot_opening_card_counts_as_its_turn_across_rounds(monkeypatch):
    manager, game, bot, human = make_bot_game(monkeypatch)

    for _ in range(4):
        opening_card = Card("9", "♣")
        second_playable_card = Card("K", "♣")
        bot.hand = [opening_card, second_playable_card, Card("Q", "♥")]
        game.current_card = opening_card
        game.current_player_index = game.players.index(bot)
        game.opening_turn_pending = True
        game.round_over = False
        game.is_active = True
        game.bridge_pending_for = None
        game.four_of_a_kind_tracker.reset()
        bot.set_default_options()
        human.websocket.sent.clear()

        await manager.run_automatic_actions(game)

        assert game.get_current_player() is human
        assert game.current_card is opening_card
        assert opening_card not in bot.hand
        assert second_playable_card in bot.hand
        assert not game.opening_turn_pending
        played_animations = [message for message in human.websocket.sent if message["type"] == "apc"]
        assert played_animations == [{"type": "apc", "card": opening_card.card_to_dict()}]


@pytest.mark.anyio
async def test_bot_opening_seven_does_not_play_a_second_matching_card(monkeypatch):
    manager, game, bot, human = make_bot_game(monkeypatch)
    opening_seven = Card("7", "♠")
    matching_queen = Card("Q", "♠")
    bot.hand = [opening_seven, matching_queen, Card("K", "♥"), Card("9", "♦"), Card("10", "♣")]
    human.hand = [Card("Q", "♠"), Card("K", "♦"), Card("9", "♣"), Card("10", "♥"), Card("A", "♦")]
    game.current_card = opening_seven
    game.current_player_index = game.players.index(bot)
    game.opening_turn_pending = True
    game.deck.deck = [Card("6", "♦"), Card("8", "♣")]
    game.deck.bounce_deck = []

    await manager.run_automatic_actions(game)

    assert game.current_card is opening_seven
    assert len(bot.hand) == 4
    assert matching_queen in bot.hand
    assert len(human.hand) == 6
    assert game.get_current_player() is human
    assert human.options.can_draw
    assert not human.options.can_skip
    played_animations = [message for message in human.websocket.sent if message["type"] == "apc"]
    assert played_animations == [{"type": "apc", "card": opening_seven.card_to_dict()}]


@pytest.mark.anyio
@pytest.mark.parametrize("opening_rank", ["6", "A"])
async def test_bot_opening_special_card_continues_only_when_rules_require_it(monkeypatch, opening_rank):
    manager, game, bot, human = make_bot_game(monkeypatch)
    opening_card = Card(opening_rank, "♠")
    legal_follow_up = Card("Q", "♠")
    bot.hand = [opening_card, legal_follow_up, Card("K", "♥"), Card("9", "♦"), Card("10", "♣")]
    human.hand = [Card("Q", "♥"), Card("K", "♦"), Card("9", "♣"), Card("10", "♥"), Card("7", "♦")]
    game.current_card = opening_card
    game.current_player_index = game.players.index(bot)
    game.opening_turn_pending = True

    await manager.run_automatic_actions(game)

    assert game.current_card is legal_follow_up
    assert len(bot.hand) == 3
    assert game.get_current_player() is human
    played_cards = [
        message["card"] for message in human.websocket.sent if message["type"] == "apc"
    ]
    assert played_cards == [opening_card.card_to_dict(), legal_follow_up.card_to_dict()]


@pytest.mark.anyio
async def test_bot_draws_two_for_eight_and_skips_even_with_a_playable_card(monkeypatch):
    manager, game, bot, human = make_bot_game(monkeypatch)
    game.current_card = Card("8", "♠")
    game.deck.deck = [Card("Q", "♦"), Card("K", "♣"), Card("A", "♦")]
    game.deck.bounce_deck = []
    bot.hand = [Card("K", "♠")]
    bot.options.must_draw = 2
    bot.options.must_skip = True
    bot.options.can_draw = False

    await manager.run_bot_turns(game)

    assert game.get_current_player() is human
    assert len(bot.hand) == 3
    assert len(game.deck.deck) == 1
    assert game.current_card.rank == "8"
    assert not bot.options.must_draw and not bot.options.must_skip


@pytest.mark.anyio
async def test_bot_draws_when_blocked_and_calls_bridge(monkeypatch):
    manager, game, bot, human = make_bot_game(monkeypatch)
    game.current_card = Card("9", "♠")
    bot.hand = [Card("Q", "♥")]
    game.deck.deck = [Card("K", "♦")]
    game.deck.bounce_deck = [Card("10", "♣")]

    await manager.run_bot_turns(game)
    assert game.get_current_player() is human
    assert len(bot.hand) == 2

    game.current_player_index = 0
    game.round_over = False
    game.bridge_pending_for = bot.user_id
    await manager.run_bot_turns(game)
    assert game.round_over and game.why_end == "bridge"


@pytest.mark.anyio
async def test_bot_controller_stops_for_humans_inactive_and_actionless_games(monkeypatch):
    manager, game, bot, human = make_bot_game(monkeypatch)
    game.opening_turn_pending = True
    await manager.run_bot_turns(game)
    assert game.get_current_player() is bot
    game.opening_turn_pending = False
    game.current_player_index = 1
    await manager.run_bot_turns(game)
    game.current_player_index = 0
    game.is_active = False
    await manager.run_bot_turns(game)
    game.is_active = True
    game.deck.deck = []
    game.deck.bounce_deck = []
    game.current_card = Card("9", "♠")
    bot.hand = [Card("Q", "♥")]
    bot.options.can_draw = False
    await manager.run_bot_turns(game)
    assert game.get_current_player() is bot


@pytest.mark.anyio
async def test_bot_uses_optional_skip_and_readable_action_delay(monkeypatch):
    manager, game, bot, human = make_bot_game(monkeypatch)
    game.current_card = Card("9", "♠")
    bot.hand = [Card("Q", "♥")]
    bot.options.can_draw = False
    bot.options.can_skip = True
    sleep = AsyncMock()
    monkeypatch.setattr("src.bot.controller.asyncio.sleep", sleep)
    manager.bot_controller.action_delay = 0.1

    await manager.run_bot_turns(game)

    sleep.assert_awaited_once_with(0.1)
    assert game.get_current_player() is human


@pytest.mark.anyio
async def test_bot_action_guard_detects_non_progressing_handlers(monkeypatch):
    manager, game, bot, _ = make_bot_game(monkeypatch)
    game.current_card = Card("9", "♠")
    bot.hand = [Card("Q", "♥")]
    manager.event_handler.handle_drew_card = AsyncMock()

    with pytest.raises(RuntimeError, match="action limit"):
        await manager.run_bot_turns(game)

    assert manager.event_handler.handle_drew_card.await_count == 256
