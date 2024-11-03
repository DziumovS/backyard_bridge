import random
from typing import List, Optional, Dict

from fastapi import WebSocket

from src.connection.manager import ConnectionManager
from src.user.models import Player
from src.game.models import Game
from src.deck.models import Deck


class GameManager:
    def __init__(self, manager: ConnectionManager):
        self.connection_manager = manager
        self.games: List[Game] = []

    def create_game(self, game: Game):
        self.games.append(game)

    def get_players(self, game_id: str) -> List[Player]:
        game = self.get_game(game_id)
        return game.players if game else []

    def remove_game(self, game_id: str):
        game = self.get_game(game_id)
        if game:
            self.games.remove(game)

    def get_game(self, game_id: str) -> Optional[Game]:
        for game in self.games:
            if game.game_id == game_id:
                return game
        return None

    def get_game_by_player_id(self, player_id: str) -> Optional[Game]:
        for game in self.games:
            for player in game.players:
                if player.user_id == player_id:
                    return game
        return None

    async def send_whose_turn(self, websocket: WebSocket, message: str, user_id: str):
        await self.connection_manager.send_message(
            websocket=websocket,
            message={
                "type": "whose_turn",
                "msg": message,
                "current_player": user_id
            }
        )

    async def send_game_data(self, player: Player, current_player: bool, game: Game,
                             chosen_suit: dict | None = None, playable_cards: bool = True):

        cards = player.prepare_playable_cards(game=game, chosen_suit=chosen_suit, playable_cards=playable_cards)

        await self.connection_manager.send_message(
            websocket=player.websocket,
            message={
                "type": "game_data",
                "hand": player.hand_to_dict(),
                "playable_cards": cards,
                "deck_len": len(game.deck),
                "current_player": current_player,
                "chosen_suit": game.chosen_suit,
                "current_card": game.current_card_to_dict(),
                "player_options": player.options_to_dict(),

                "scores_rate": f"<b>x{game.deck.scores_rate}</b>",
                "scores_rate_up": True if game.deck.scores_rate > 1 and not game.deck.bounce_deck else False,

                "players_hands": [{"player_id": p.user_id, "hand_len": len(p.hand)} for p in game.players]  # to do
            }
        )

    async def handle_game_over(self, current_player: Player, next_player: Player, game: Game):
        if next_player.options.must_draw:
            message = f"You got {"2 cards" if game.current_card.rank == "8" else "1 card"} from the deck."

            if not game.deck.deck and not game.deck.bounce_deck:
                game.deck.add_to_deck_random_card()
                message = f"You got {"2 random cards" if game.current_card.rank == "8" else "1 random card"}."

            next_player.draw_card(deck=game.deck)

            await self.send_whose_turn(
                websocket=next_player.websocket,
                message=message,
                user_id=next_player.user_id
            )

            for player in game.players:
                is_current_player = player.user_id == next_player.user_id
                await self.send_game_data(
                    player=player,
                    current_player=is_current_player,
                    game=game,
                    chosen_suit=game.chosen_suit,
                    playable_cards=False
                )

            await self.connection_manager.send_message(
                websocket=next_player.websocket,
                message={"type": "game_over_draw_card"})
            next_player.options.must_draw -= 1

        elif not next_player.options.must_draw:
            game.calculate_scores()

            message, results = game.get_game_over_message(current_player=current_player)

            for player in game.players:
                await self.connection_manager.send_message(
                    websocket=player.websocket,
                    message={
                        "type": "game_over",
                        "error_msg": message,
                        "widget_msg": results,
                        "player_scores": player.scores
                    }
                )

    async def handle_disconnect_game(self, player_id: str, error: bool = False):
        game = self.get_game_by_player_id(player_id=player_id)
        if game:
            left_player = game.get_player_or_none(user_id=player_id)
            game.remove_player(user_id=player_id)
            message = f"Player <b>{left_player.user_name}</b> has left the game."

            while left_player.hand:
                game.deck.bounce_deck.append(left_player.hand.pop())

            try:
                if player_id == game.get_current_player().user_id:
                    game.next_player()
            except IndexError:
                return

            next_player = game.get_current_player()

            await self.connection_manager.broadcast(
                websockets=game.get_players_websocket(),
                message={"type": "users_update", "users": game.get_players()}
            )

            await self.connection_manager.broadcast(
                websockets=game.get_players_websocket(),
                message={"type": "show_error", "msg": message}
            )

            for player in game.players:
                is_current_player = player.user_id == next_player.user_id
                message = "It's your turn!" if is_current_player else f"It's {next_player.user_name}'s turn!"

                await self.send_whose_turn(
                    websocket=player.websocket,
                    message=message,
                    user_id=next_player.user_id
                )

                await self.send_game_data(
                    player=player,
                    current_player=is_current_player,
                    game=game,
                    chosen_suit=game.chosen_suit
                )

            await self.connection_manager.disconnect(websocket=left_player.websocket, error=error)

            if len(game.players) <= 1:
                game.is_active = False
                message = (f"{left_player.user_name} has left the game, not enough players to continue the game. "
                           f"Returning to the home page...")

                await self.connection_manager.broadcast(
                    websockets=game.get_players_websocket(),
                    message={"type": "not_enough_players", "msg": message})

                for player in game.players:
                    await self.connection_manager.disconnect(websocket=player.websocket)

                self.remove_game(game.game_id)
