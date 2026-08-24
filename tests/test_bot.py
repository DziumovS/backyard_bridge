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
async def test_bot_completes_required_draw_and_skip(monkeypatch):
    manager, game, bot, human = make_bot_game(monkeypatch)
    game.current_card = Card("8", "♠")
    game.deck.deck = [Card("Q", "♦")]
    game.deck.bounce_deck = [Card("K", "♣")]
    bot.hand = [Card("9", "♥")]
    bot.options.must_draw = 1
    bot.options.must_skip = True
    bot.options.can_draw = False

    await manager.run_bot_turns(game)

    assert game.get_current_player() is human
    assert len(bot.hand) == 2
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
