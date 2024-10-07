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
                             to_dict: bool = True, playable_cards: bool = True):
        if playable_cards:
            playable_cards = player.get_playable_cards(current_card=game.current_card, to_dict=to_dict)
        else:
            playable_cards = ()

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
            }
        )
