from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.game.enums import EventType
from src.lobby.router import game_manager


router = APIRouter(
    prefix="",
    tags=["Game"]
)


@router.websocket("/ws/game/{game_id}/{user_id}")
async def websocket_game(websocket: WebSocket, game_id: str, user_id: str):
    game = game_manager.get_game(game_id=game_id)
    await game_manager.connection_manager.connect(websocket=websocket)

    game.add_player_websocket(player_id=user_id, websocket=websocket)

    await game.wait_until_all_ready()

    try:
        while game.is_active:

            data = await websocket.receive_json()

            match data["type"]:
                case EventType.GAME_STARTED.value:
                    await game_manager.event_handler.handle_game_started(player_id=user_id, game=game)

                case EventType.PLAYED_CARD.value:
                    await game_manager.event_handler.handle_played_card(
                        played_card=data["card"],
                        chosen_suit=data["chosen_suit"],
                        game=game
                    )

                case EventType.DREW_CARD.value:
                    await game_manager.event_handler.handle_drew_card(game=game)

                case EventType.SKIP_TURN.value:
                    await game_manager.event_handler.handle_skip_turn(game=game)

                case EventType.SHOW_MY_MOVE.value:
                    await game_manager.event_handler.handle_show_my_move(game=game, data=data)

                case EventType.GAME_OVER.value:
                    await game_manager.event_handler.handle_game_over(game=game)

                case EventType.RESET_GAME.value:
                    await game_manager.event_handler.handle_reset_game(game=game)

    except WebSocketDisconnect as err:
        match err.code:
            case 1001 | 1006:
                await game_manager.event_handler.handle_disconnect_game(player_id=user_id, error=True)
            case 1012:
                player = game.get_player_or_none(user_id=user_id)
                await game_manager.connection_manager.disconnect(websocket=player.websocket, error=True)
            case _:
                pass
