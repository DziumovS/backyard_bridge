from enum import StrEnum


class AutomaticAction(StrEnum):
    OPENING_TURN = "opening_turn"
    BOT_TURN = "bot_turn"
    DRAW = "draw"
    SKIP = "skip"


class AutomaticTurnController:
    def __init__(self, game_manager):
        self.game_manager = game_manager

    @staticmethod
    def next_action(game) -> AutomaticAction | None:
        if not game.is_active or game.round_over:
            return None

        player = game.get_current_player()
        if game.bridge_pending_for == player.user_id:
            return None
        if game.opening_turn_pending:
            return AutomaticAction.OPENING_TURN if player.is_bot else None
        if player.is_bot:
            return AutomaticAction.BOT_TURN
        if player.options.must_draw:
            return AutomaticAction.DRAW
        if player.options.must_skip:
            return AutomaticAction.SKIP

        playable_cards = player.get_playable_cards(
            current_card=game.current_card,
            chosen_suit=game.chosen_suit,
        )
        only_draw_is_available = (
            player.options.can_draw
            and not player.options.can_skip
            and not playable_cards
        )
        return AutomaticAction.DRAW if only_draw_is_available else None

    async def run(self, game) -> None:
        for _ in range(256):
            action = self.next_action(game)
            if action is None:
                return

            player = game.get_current_player()
            if action is AutomaticAction.OPENING_TURN:
                card = game.current_card
                chosen_suit = (
                    self.game_manager.bot_controller.strategy.choose_suit(player, card)
                    if card.rank == "J"
                    else None
                )
                await self.game_manager.event_handler.handle_played_card(
                    card.card_to_dict(),
                    chosen_suit,
                    game,
                    player.user_id,
                )
                continue

            if action is AutomaticAction.BOT_TURN:
                await self.game_manager.bot_controller.run_until_human_turn(game)
                continue

            if action is AutomaticAction.DRAW:
                if game.deck.is_decks_empty():
                    return
                await self.game_manager.event_handler.handle_drew_card(
                    game,
                    player.user_id,
                    animate_current=True,
                )
                continue

            await self.game_manager.event_handler.handle_skip_turn(game, player.user_id)

        raise RuntimeError("Automatic action limit exceeded")
