from typing import List, Optional

from fastapi import WebSocket

from src.connection.manager import ConnectionManager
from src.enums.game import EventType
from src.user.models import Player
from src.game.models import Game
from src.game.handlers import EventHandler


class GameManager:
    def __init__(self, manager: ConnectionManager):
        self.connection_manager = manager
        self.games: List[Game] = []
        self.event_handler = EventHandler(game_manager_instance=self)

    def create_game(self, game: Game):
        self.games.append(game)

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
                "type": EventType.WHOSE_TURN.value,
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
                "type": EventType.GAME_DATA.value,
                "hand": player.hand_to_dict(),
                "playable_cards": cards,
                "deck_len": len(game.deck),
                "current_player": current_player,
                "chosen_suit": game.chosen_suit,
                "current_card": game.current_card_to_dict(),
                "player_options": player.options_to_dict(),
                "scores_rate": f"x{game.deck.scores_rate}",
                "players_hands": [{"player_id": p.user_id, "hand_len": len(p.hand)} for p in game.players]
            }
        )
