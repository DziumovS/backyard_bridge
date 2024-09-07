from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.lobby.router import connection_manager, game_manager


router = APIRouter(
    prefix="",
    tags=["Game"]
)


@router.websocket("/ws/game/{game_id}/{user_id}")
async def websocket_game(websocket: WebSocket, game_id: str, user_id: str):
    await connection_manager.connect(websocket=websocket)
    players = game_manager.get_players(game_id)
    for player in players:
        if player.user_id == user_id:
            player.websocket = websocket
            break

    try:
        while True:
            data = await websocket.receive_text()
            current_player = game_manager.get_player_or_none(game_id=game_id, user_id=user_id)
            for player in game_manager.games[game_id]:
                message_to_send = f"{current_player.user_name}: {data}"
                await connection_manager.send_message(
                    websocket=player.websocket,
                    message=message_to_send
                )
    except WebSocketDisconnect:
        pass
