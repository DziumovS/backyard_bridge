import asyncio
import os

from src.bot.strategy import BotStrategy


def default_action_delay() -> float:
    raw_value = os.getenv("BACKYARD_BRIDGE_BOT_ACTION_DELAY", "0.45")
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return 0.45


class BotController:
    def __init__(self, game_manager, strategy: BotStrategy | None = None, action_delay: float | None = None):
        self.game_manager = game_manager
        self.strategy = strategy or BotStrategy()
        self.action_delay = default_action_delay() if action_delay is None else action_delay

    async def run_until_human_turn(self, game) -> None:
        for _ in range(256):
            if not game.is_active or game.round_over:
                return

            player = game.get_current_player()
            if not player.is_bot:
                return
            if game.opening_turn_pending:
                return

            if self.action_delay:
                await asyncio.sleep(self.action_delay)

            handler = self.game_manager.event_handler
            if self.strategy.should_call_bridge(game, player):
                await handler.handle_game_over(game, player.user_id)
            elif player.options.must_draw:
                await handler.handle_drew_card(game, player.user_id)
            elif player.options.must_skip:
                await handler.handle_skip_turn(game, player.user_id)
            else:
                card = self.strategy.choose_card(game, player)
                if card is not None:
                    chosen_suit = self.strategy.choose_suit(player, card) if card.rank == "J" else None
                    await handler.handle_played_card(
                        card.card_to_dict(),
                        chosen_suit,
                        game,
                        player.user_id,
                    )
                elif player.options.can_draw and not game.deck.is_decks_empty():
                    await handler.handle_drew_card(game, player.user_id)
                elif player.options.can_skip or game.current_card.rank == "J":
                    await handler.handle_skip_turn(game, player.user_id)
                else:
                    return

        raise RuntimeError("Bot action limit exceeded")
