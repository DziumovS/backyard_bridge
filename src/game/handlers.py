from src.game.enums import EventType
from src.user.models import Player
from src.deck.models import Card


class CardHandler:
    def __init__(self, game_instance):
        self.game_instance = game_instance

    def handle_card_six(self, current_player: Player) -> None:
        decks_empty = self.game_instance.deck.is_decks_empty()
        playable_cards = current_player.get_playable_cards(
            current_card=self.game_instance.current_card,
            chosen_suit=self.game_instance.chosen_suit,
        )
        if playable_cards:
            current_player.options.can_skip = False
            current_player.options.can_draw = not decks_empty
        else:
            current_player.options.must_draw = 0 if decks_empty else current_player.options.must_draw + 1

    def _handle_card_six(self, current_player: Player, card: Card) -> None:
        self.game_instance.remove_played_card(current_player=current_player, card=card)
        self.handle_card_six(current_player=current_player)

    def _handle_card_seven(self, current_player: Player, card: Card) -> None:
        self.game_instance.remove_played_card(current_player=current_player, card=card)
        current_player.options.must_skip = True

        next_player = self.game_instance.get_next_player()
        next_player.set_default_options()
        next_player.options.must_draw += 1

    def _handle_card_eight(self, current_player: Player, card: Card) -> None:
        self.game_instance.remove_played_card(current_player=current_player, card=card)
        current_player.options.must_skip = True

        next_player = self.game_instance.get_next_player()
        next_player.set_default_options()
        next_player.options.must_draw += 2
        next_player.options.must_skip = True

    def _handle_card_jack(self, current_player: Player, card: Card) -> None:
        self.game_instance.remove_played_card(current_player=current_player, card=card)
        current_player.options.can_draw = False
        current_player.options.can_skip = True

        if current_player.user_id not in self.game_instance.last_cards_j:
            self.game_instance.last_cards_j[current_player.user_id] = 1
        else:
            self.game_instance.last_cards_j[current_player.user_id] += 1

        if not current_player.get_playable_cards(current_card=self.game_instance.current_card, j=True):
            current_player.options.must_skip = True

        next_player = self.game_instance.get_next_player()
        next_player.set_default_options()

    def _handle_card_ace(self, current_player: Player, card: Card) -> None:
        self.game_instance.remove_played_card(current_player=current_player, card=card)
        current_player.options.must_skip = True

        next_player = self.game_instance.get_next_player()
        next_player.set_default_options()
        next_player.options.must_skip = True

    def _handle_normal_card(self, current_player: Player, card: Card) -> None:
        self.game_instance.remove_played_card(current_player=current_player, card=card)
        current_player.set_default_options()
        current_player.options.must_skip = True

    def handle_special_cards(self, current_player: Player, card: Card) -> None:
        match self.game_instance.current_card.rank:
            case "6":
                self._handle_card_six(current_player=current_player, card=card)
            case "7":
                self._handle_card_seven(current_player=current_player, card=card)
            case "8":
                self._handle_card_eight(current_player=current_player, card=card)
            case "J":
                self._handle_card_jack(current_player=current_player, card=card)
            case "A":
                self._handle_card_ace(current_player=current_player, card=card)
            case _:
                self._handle_normal_card(current_player=current_player, card=card)


class EventHandler:
    def __init__(self, game_manager_instance):
        self.gm = game_manager_instance

    async def _handle_game_over(self, current_player: Player, next_player: Player, game) -> None:
        if next_player.options.must_draw:
            message = f"You got {"2 cards" if game.current_card.rank == "8" else "1 card"} from the deck."

            if not game.deck.deck and not game.deck.bounce_deck:
                game.deck.add_to_deck_random_card()
                message = f"You got {"2 random cards" if game.current_card.rank == "8" else "1 random card"}."

            next_player.draw_card(deck=game.deck)

            await self.gm.send_whose_turn(websocket=next_player.websocket, message=message, user_id=next_player.user_id)

            for player in game.players:
                is_current_player = player.user_id == next_player.user_id
                await self.gm.send_game_data(
                    player=player,
                    current_player=is_current_player,
                    game=game,
                    chosen_suit=game.chosen_suit,
                    playable_cards=False
                )

            await self.gm.connection_manager.send_message(
                websocket=next_player.websocket,
                message={"type": EventType.GAME_OVER_DRAW_CARD.value}
            )
            next_player.options.must_draw -= 1

        elif not next_player.options.must_draw:
            players_scores = game.calculate_scores()

            message, results = game.get_game_over_message(current_player=current_player)

            for player in game.players:
                player.set_default_options(can_draw=False)
                is_current_player = player.user_id == next_player.user_id

                await self.gm.send_game_data(
                    player=player,
                    current_player=is_current_player,
                    game=game,
                    chosen_suit=game.chosen_suit,
                    playable_cards=False
                )

                await self.gm.connection_manager.send_message(
                    websocket=player.websocket,
                    message={
                        "type": EventType.GAME_OVER.value,
                        "players_scores": players_scores,
                        "error_msg": message,
                        "widget_msg": results,
                        "player_scores": player.scores
                    }
                )

    async def handle_disconnect_game(self, player_id: str, error: bool = False) -> None:
        game = self.gm.get_game_by_player_id(player_id=player_id)
        if game:
            left_player = game.get_player_or_none(user_id=player_id)

            if player_id == game.get_current_player().user_id:
                game.next_player()

            while left_player.hand:
                game.deck.bounce_deck.append(left_player.hand.pop())

            next_player = game.get_current_player()

            game.remove_player(player=left_player)
            message = f"Player <b>{left_player.user_name}</b> has left the game."

            await self.gm.connection_manager.broadcast(
                websockets=game.get_players_websocket(),
                message={"type": EventType.LEAVE_GAME.value, "player_id": left_player.user_id}
            )

            await self.gm.connection_manager.broadcast(
                websockets=game.get_players_websocket(),
                message={"type": EventType.SHOW_ERROR.value, "msg": message}
            )

            for player in game.players:
                is_current_player = player.user_id == next_player.user_id
                message = "It's your turn!" if is_current_player else f"It's {next_player.user_name}'s turn!"

                await self.gm.send_whose_turn(websocket=player.websocket, message=message, user_id=next_player.user_id)

                await self.gm.send_game_data(
                    player=player,
                    current_player=is_current_player,
                    game=game,
                    chosen_suit=game.chosen_suit
                )

            await self.gm.connection_manager.disconnect(websocket=left_player.websocket, error=error)

            if len(game.players) <= 1:
                game.is_active = False
                message = (f"<b>{left_player.user_name}</b> has left the game, not enough players to continue the game."
                           f" Returning to the home page...")

                await self.gm.connection_manager.broadcast(
                    websockets=game.get_players_websocket(),
                    message={"type": EventType.NOT_ENOUGH_PLAYERS.value, "msg": message})

                for player in game.players:
                    await self.gm.connection_manager.disconnect(websocket=player.websocket)

                self.gm.remove_game(game.game_id)

    async def handle_game_started(self, player_id: str, game) -> None:
        player = game.get_player_or_none(user_id=player_id)
        current_player = game.get_current_player()
        is_current_player = game.is_current_player(player_id=player_id)
        message = "It's your turn!" if is_current_player else f"It's {current_player.user_name}'s turn!"

        await self.gm.send_whose_turn(websocket=player.websocket, message=message, user_id=current_player.user_id)

        await self.gm.send_game_data(player=player, current_player=is_current_player, game=game, playable_cards=False)

        if is_current_player:
            await self.gm.connection_manager.send_message(
                websocket=current_player.websocket,
                message={
                    "type": EventType.FIRST_TURN.value,
                    "current_card": game.current_card.card_to_dict()
                }
            )
        game.four_of_a_kind_tracker.current_rank = game.current_card.rank

    async def handle_played_card(self, played_card: dict, chosen_suit: str | None, game) -> None:
        current_player = game.get_current_player()
        previous_card = game.current_card
        card = current_player.dict_to_card(card=played_card)
        game.current_card = card

        game.chosen_suit = {
            "suit": chosen_suit,
            "color": game.deck.color_map[chosen_suit],
            "chooser_id": current_player.user_id
        } if chosen_suit else None

        if current_player.user_id not in game.last_cards_j:
            game.last_cards_j.clear()

        game.card_handler.handle_special_cards(
            current_player=current_player,
            card=previous_card if previous_card != card else None
        )

        next_player = game.get_next_player()

        if current_player.has_won(card=card):
            if not game.why_end:
                game.why_end = "empty_hand"
            current_player.set_default_options(can_draw=False)
            await self._handle_game_over(current_player=current_player, next_player=next_player, game=game)

        if game.deck.is_decks_empty_for_eight(card=card):
            if not game.why_end:
                game.why_end = "empty_deck"
            await self._handle_game_over(current_player=current_player, next_player=next_player, game=game)

        for player in game.players:
            await self.gm.send_game_data(
                player=player,
                current_player=player.user_id == current_player.user_id,
                game=game,
                chosen_suit=game.chosen_suit
            )

        if current_player.options.must_skip and not current_player.options.must_draw or card.rank in ("6", "J"):
            if not game.why_end:
                if game.is_it_bridge(card=card):
                    message = "You have played the 4-th card in a row of the same value. Would you say bridge?"
                    await self.gm.connection_manager.send_message(
                        websocket=current_player.websocket,
                        message={
                            "type": EventType.IS_IT_BRIDGE.value,
                            "msg": message,
                            "current_card": played_card
                        }
                    )

    async def handle_drew_card(self, game) -> None:
        current_player = game.get_current_player()
        current_player.draw_card(deck=game.deck)

        playable_cards = current_player.get_playable_cards(current_card=game.current_card, chosen_suit=game.chosen_suit)

        if current_player.options.must_draw:
            current_player.options.must_draw -= 1
        elif current_player.options.must_skip:
            current_player.options.must_skip = False
        elif current_player.options.can_draw and not playable_cards:
            current_player.options.must_skip = True
        elif current_player.options.can_draw:
            current_player.options.can_draw = False
            current_player.options.can_skip = True

        if game.current_card.rank == "6":
            game.card_handler.handle_card_six(current_player=current_player)

        for player in game.players:
            await self.gm.send_game_data(
                player=player,
                current_player=player.user_id == current_player.user_id,
                game=game,
                chosen_suit=game.chosen_suit
            )

        if all((not current_player.options.can_draw, current_player.options.can_skip)):
            current_player.set_default_options()

    async def handle_skip_turn(self, game) -> None:
        current_player = game.get_current_player()

        if current_player.user_id not in game.last_cards_j:
            game.last_cards_j.clear()
        if game.chosen_suit and game.chosen_suit["chooser_id"]:
            game.chosen_suit["chooser_id"] = None

        if current_player.options.must_skip or game.current_card.rank == "J":
            current_player.set_default_options()

        game.next_player()

        next_player = game.get_current_player()
        playable_cards = next_player.get_playable_cards(current_card=game.current_card, chosen_suit=game.chosen_suit)

        if game.deck.is_decks_empty():
            next_player.options.must_draw = 0
            next_player.options.can_draw = False

        for player in game.players:
            is_current_player = player.user_id == next_player.user_id
            message = "It's your turn!" if is_current_player else f"It's {next_player.user_name}'s turn!"

            await self.gm.send_whose_turn(websocket=player.websocket, message=message, user_id=next_player.user_id)

            await self.gm.send_game_data(
                player=player,
                current_player=is_current_player,
                game=game,
                chosen_suit=game.chosen_suit
            )
        if game.deck.is_decks_empty():
            if not playable_cards:
                if not game.why_end:
                    game.why_end = "empty_deck"
                await self._handle_game_over(current_player=next_player, next_player=next_player, game=game)

    async def handle_show_my_move(self, game, data: dict) -> None:
        current_player = game.get_current_player()
        next_player = game.get_next_player()

        player_to_skip = next_player if game.why_end is not None else current_player
        players_to_notify = [player for player in game.players if player.user_id != player_to_skip.user_id]

        if "card" in data:
            message = {"type": EventType.ANIMATE_PLAYED_CARD.value, "card": data["card"]}
        else:
            message = {
                "type": EventType.ANIMATE_DRAW_CARD.value,
                "current_player": next_player.user_id if game.why_end is not None else None
            }

        for player in players_to_notify:
            await self.gm.connection_manager.send_message(websocket=player.websocket, message=message)

    async def handle_game_over(self, game) -> None:
        if not game.why_end:
            game.why_end = "bridge"

        current_player = game.get_current_player()
        next_player = game.get_next_player()

        await self._handle_game_over(current_player=current_player, next_player=next_player, game=game)

    async def handle_reset_game(self, game) -> None:
        game.reset_game()

        current_player = game.get_current_player()

        players = game.players

        for player in players:
            is_current_player = player.user_id == current_player.user_id
            message = "It's your turn!" if is_current_player else f"It's {current_player.user_name}'s turn!"

            await self.gm.connection_manager.send_message(
                websocket=player.websocket,
                message={
                    "type": EventType.GAME_RESET.value,
                    "players_scores": [{"player_id": player.user_id, "scores": player.scores} for player in players],
                    "player_scores": player.scores}
            )

            await self.gm.send_whose_turn(websocket=player.websocket, message=message, user_id=current_player.user_id)

            await self.gm.send_game_data(
                player=player,
                current_player=is_current_player,
                game=game,
                playable_cards=False
            )

            if is_current_player:
                await self.gm.connection_manager.send_message(
                    websocket=current_player.websocket,
                    message={
                        "type": EventType.FIRST_TURN.value,
                        "current_card": game.current_card.card_to_dict()
                    }
                )

        game.four_of_a_kind_tracker.current_rank = game.current_card.rank
