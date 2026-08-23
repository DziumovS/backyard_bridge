import asyncio

from fastapi import WebSocket

from src.connection.manager import ConnectionManager
from src.game.enums import EventType
from src.user.models import Player
from src.game.models import Game
from src.game.handlers import EventHandler


class GameManager:
    def __init__(self, manager: ConnectionManager):
        self.connection_manager = manager
        self.games: list[Game] = []
        self.event_handler = EventHandler(game_manager_instance=self)

    def create_game(self, game: Game) -> None:
        self.games.append(game)

    def remove_game(self, game_id: str) -> None:
        game = self.get_game(game_id)
        if game:
            self.games.remove(game)

    def get_game(self, game_id: str) -> Game | None:
        for game in self.games:
            if game.game_id == game_id:
                return game
        return None

    def get_game_by_player_id(self, player_id: str) -> Game | None:
        for game in self.games:
            for player in game.players:
                if player.user_id == player_id:
                    return game
        return None

    async def abort_startup(self, game: Game, websocket: WebSocket) -> None:
        game.is_active = False
        await self.connection_manager.send_message(
            websocket,
            {"type": EventType.SHOW_ERROR.value, "msg": "Game startup timed out. Please try again."},
        )
        await self.connection_manager.disconnect(websocket)
        self.remove_game(game.game_id)

    async def send_whose_turn(self, websocket: WebSocket, message: str, user_id: str) -> None:
        await self.connection_manager.send_message(
            websocket=websocket,
            message={
                "type": EventType.WHOSE_TURN.value,
                "msg": message,
                "current_player": user_id
            }
        )

    async def send_game_data(self, player: Player, current_player: bool, game: Game,
                             chosen_suit: dict | None = None, playable_cards: bool = True) -> None:

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
                "is_host": player.user_id == game.host_id,
                "round_over": game.round_over,
                "players": [
                    {"user_id": current.user_id, "user_name": current.user_name}
                    for current in game.players
                ],
                "players_hands": [{"player_id": p.user_id, "hand_len": len(p.hand)} for p in game.players]
            }
        )

    async def send_game_data_to_all(
        self,
        game: Game,
        current_player_id: str,
        chosen_suit: dict | None = None,
        playable_cards: bool = True,
    ) -> None:
        await asyncio.gather(*(
            self.send_game_data(
                player=player,
                current_player=player.user_id == current_player_id,
                game=game,
                chosen_suit=chosen_suit,
                playable_cards=playable_cards,
            )
            for player in game.players
        ))

    async def send_turn_and_game_data_to_all(self, game: Game, current_player: Player) -> None:
        async def notify(player: Player) -> None:
            is_current_player = player.user_id == current_player.user_id
            message = "It's your turn!" if is_current_player else f"It's {current_player.user_name}'s turn!"
            await self.send_whose_turn(
                websocket=player.websocket,
                message=message,
                user_id=current_player.user_id,
            )
            await self.send_game_data(
                player=player,
                current_player=is_current_player,
                game=game,
                chosen_suit=game.chosen_suit,
            )

        await asyncio.gather(*(notify(player) for player in game.players))
