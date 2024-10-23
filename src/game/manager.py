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
