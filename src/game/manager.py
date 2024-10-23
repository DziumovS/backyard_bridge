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

        if player.options.must_draw or player.options.must_skip or not playable_cards:
            playable_cards = ()
        else:
            if game.current_card.rank == "J" and game.chosen_suit and game.chosen_suit["chooser_id"] == player.user_id:
                playable_cards = player.get_playable_cards(current_card=game.current_card, to_dict=True, j=True)
            else:
                playable_cards = player.get_playable_cards(
                    current_card=game.current_card,
                    chosen_suit=chosen_suit,
                    to_dict=True
                )

        await self.connection_manager.send_message(
            websocket=player.websocket,
            message={
                "type": "game_data",
                "hand": player.hand_to_dict(),
                "playable_cards": playable_cards,
                "deck_len": len(game.deck),
                "current_player": current_player,
                "chosen_suit": game.chosen_suit,
                "current_card": game.current_card_to_dict(),
                "player_options": player.options_to_dict(),

                "scores_rate": game.deck.scores_rate  # do it!
            }
        )

    async def handle_disconnect_game(self, player_id: str, error: bool = False):
        game = self.get_game_by_player_id(player_id=player_id)
        if game:
            left_player = game.get_player_or_none(user_id=player_id)
            game.remove_player(user_id=player_id)

            while left_player.hand:
                game.deck.bounce_deck.append(left_player.hand.pop())

            if player_id == game.get_current_player().user_id:
                game.next_player()

            next_player = game.get_current_player()

            for player in game.players:
                is_current_player = player.user_id == next_player.user_id
                pre_message = f"Player {left_player.user_name} has left the game. "
                message = "It's your turn!" if is_current_player else f"It's {next_player.user_name}'s turn!"

                await self.send_whose_turn(
                    websocket=player.websocket,
                    message=f"{pre_message}{message}",
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
                message = (
                    f"With {left_player.user_name} gone, there aren't enough players left in the game to keep it going."
                )

                await self.connection_manager.broadcast(
                    websockets=game.get_players_websocket(),
                    message={
                        "type": "not_enough_players",
                        "msg": message
                    }
                )

                for player in game.players:
                    await self.connection_manager.disconnect(websocket=player.websocket)

                self.remove_game(game.game_id)
