import asyncio
import time

from fastapi import WebSocket

from src.connection.manager import ConnectionManager
from src.game.enums import EventType
from src.user.models import Player
from src.game.models import Game
from src.game.handlers import EventHandler
from src.game.automation import AutomaticTurnController
from src.bot.controller import BotController
from src.config import get_reconnect_grace_seconds


class GameManager:
    def __init__(self, manager: ConnectionManager):
        self.connection_manager = manager
        self.games: dict[str, Game] = {}
        self._game_ids_by_player: dict[str, str] = {}
        self._disconnect_tasks: dict[str, asyncio.Task] = {}
        self._disconnect_deadlines: dict[str, float] = {}
        self.reconnect_grace_seconds = get_reconnect_grace_seconds()
        self.event_handler = EventHandler(game_manager_instance=self)
        self.bot_controller = BotController(self)
        self.automatic_turn_controller = AutomaticTurnController(self)

    def create_game(self, game: Game) -> None:
        self.games[game.game_id] = game
        for player in game.players:
            self._game_ids_by_player[player.user_id] = game.game_id

    def add_player(self, game: Game, player: Player) -> None:
        game.players.append(player)
        self._game_ids_by_player[player.user_id] = game.game_id

    def remove_player(self, game: Game, player: Player) -> None:
        self.cancel_disconnect(player.user_id)
        current_player_id = game.get_current_player().user_id if game.players else None
        game.remove_player(player)
        self._game_ids_by_player.pop(player.user_id, None)
        if current_player_id and game.players:
            preserved_index = next(
                (
                    index for index, current in enumerate(game.players)
                    if current.user_id == current_player_id
                ),
                None,
            )
            game.current_player_index = (
                preserved_index
                if preserved_index is not None
                else game.current_player_index % len(game.players)
            )
        else:
            game.current_player_index = 0

    def remove_game(self, game_id: str) -> None:
        game = self.games.pop(game_id, None)
        if game:
            for player in game.players:
                self.cancel_disconnect(player.user_id)
                self._game_ids_by_player.pop(player.user_id, None)

    def clear(self) -> None:
        for task in self._disconnect_tasks.values():
            task.cancel()
        self._disconnect_tasks.clear()
        self._disconnect_deadlines.clear()
        self.games.clear()
        self._game_ids_by_player.clear()

    def get_game(self, game_id: str) -> Game | None:
        return self.games.get(game_id)

    def get_game_by_player_id(self, player_id: str) -> Game | None:
        game_id = self._game_ids_by_player.get(player_id)
        return self.games.get(game_id) if game_id else None

    def cancel_disconnect(self, player_id: str) -> None:
        task = self._disconnect_tasks.pop(player_id, None)
        self._disconnect_deadlines.pop(player_id, None)
        if task:
            task.cancel()

    def reconnect_seconds_left(self, player_id: str) -> float:
        deadline = self._disconnect_deadlines.get(player_id)
        if deadline is None:
            return self.reconnect_grace_seconds
        return max(0.0, deadline - time.monotonic())

    def schedule_disconnect(self, player_id: str, websocket: WebSocket) -> bool:
        game = self.get_game_by_player_id(player_id)
        player = game.get_player_or_none(player_id) if game else None
        if player is None or player.websocket is not websocket:
            return False
        player.websocket = None
        self.cancel_disconnect(player_id)
        self._disconnect_deadlines[player_id] = time.monotonic() + self.reconnect_grace_seconds

        async def expire() -> None:
            try:
                await asyncio.sleep(self.reconnect_grace_seconds)
                self._disconnect_tasks.pop(player_id, None)
                self._disconnect_deadlines.pop(player_id, None)
                await self.event_handler.handle_disconnect_game(player_id=player_id, error=True)
            except asyncio.CancelledError:
                pass

        self._disconnect_tasks[player_id] = asyncio.create_task(expire())
        return True

    def resume_player(self, game: Game, player: Player, websocket: WebSocket) -> bool:
        if player.websocket is not None:
            return False
        self.cancel_disconnect(player.user_id)
        player.websocket = websocket
        game.check_all_players_connected()
        return True

    async def abort_startup(self, game: Game, websocket: WebSocket) -> None:
        game.is_active = False
        await self.connection_manager.send_message(
            websocket,
            {"type": EventType.SHOW_ERROR.value, "msg": "Game startup timed out. Try again."},
        )
        await self.connection_manager.disconnect(websocket)
        self.remove_game(game.game_id)

    async def send_whose_turn(self, websocket: WebSocket, message: str, user_id: str) -> None:
        if websocket is None:
            return
        await self.connection_manager.send_message(
            websocket=websocket,
            message={
                "type": EventType.WHOSE_TURN.value,
                "msg": message,
                "current_player": user_id
            }
        )

    async def send_game_data(
        self,
        player: Player,
        current_player: bool,
        game: Game,
        chosen_suit: dict | None = None,
        playable_cards: bool = True,
        scores_rate_changed: bool = False,
    ) -> None:

        if player.websocket is None:
            return

        cards = player.prepare_playable_cards(game=game, chosen_suit=chosen_suit, playable_cards=playable_cards)
        automatic_action_pending = (
            current_player
            and not player.is_bot
            and self.automatic_turn_controller.next_action(game) is not None
        )

        await self.connection_manager.send_message(
            websocket=player.websocket,
            message={
                "type": EventType.GAME_DATA.value,
                "hand": player.hand_to_dict(),
                "playable_cards": cards,
                "deck_len": len(game.deck),
                "current_player": current_player,
                "automatic_action_pending": automatic_action_pending,
                "chosen_suit": game.chosen_suit,
                "current_card": game.current_card_to_dict(),
                "player_options": player.options_to_dict(),
                "scores_rate": f"x{game.deck.scores_rate}",
                "scores_rate_changed": scores_rate_changed,
                "is_host": player.user_id == game.host_id,
                "round_over": game.round_over,
                "players": [
                    {
                        "user_id": current.user_id,
                        "user_name": current.user_name,
                        "is_bot": current.is_bot,
                        "scores": current.scores,
                    }
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
        scores_rate_changed: bool = False,
    ) -> None:
        await asyncio.gather(*(
            self.send_game_data(
                player=player,
                current_player=player.user_id == current_player_id,
                game=game,
                chosen_suit=chosen_suit,
                playable_cards=playable_cards,
                scores_rate_changed=scores_rate_changed,
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

        await asyncio.gather(*(notify(player) for player in game.players if player.websocket is not None))

    async def run_bot_turns(self, game: Game) -> None:
        await self.bot_controller.run_until_human_turn(game)

    async def run_automatic_actions(self, game: Game) -> None:
        await self.automatic_turn_controller.run(game)
