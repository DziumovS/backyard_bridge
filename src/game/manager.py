import random
from typing import List, Optional, Dict

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
