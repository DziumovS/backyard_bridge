from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from src.connection.manager import ConnectionManager
from src.lobby.manager import LobbyManager
from src.game.manager import GameManager
from src.user.models import User


router = APIRouter(
    prefix="",
    tags=["Lobby"]
)


connection_manager = ConnectionManager()
lobby_manager = LobbyManager(connection_manager)
game_manager = GameManager(connection_manager)


@router.get("/check_lobby/{lobby_id}")
async def check_lobby(lobby_id: str):
    lobby = lobby_manager.lobbies.get(lobby_id)
    exists = lobby is not None and len(lobby.users) < 6
    return JSONResponse(content={"exists": exists})


@router.websocket("/ws/lobby/{user_id}")
async def websocket_lobby(websocket: WebSocket, user_id: str):
    await connection_manager.connect(websocket=websocket)
    user = User(user_id=user_id, websocket=websocket, user_name=user_id)

    try:
        while True:
            data = await websocket.receive_json()
            if "user_name" in data and data["user_name"] != user.user_id:
                user.user_name = data["user_name"]

            match data["type"]:
                case "create_lobby":
                    await lobby_manager.handle_create_lobby(user=user, websocket=websocket)

                case "close_lobby":
                    lobby = lobby_manager.get_lobby_by_user_id(user_id=user_id)
                    if lobby:
                        await lobby_manager.handle_disconnect_lobby(user_id=user_id)
                    break

                case "join_lobby":
                    lobby_id = data.get("lobby_id")
                    await lobby_manager.handle_join_lobby(user=user, websocket=websocket, lobby_id=lobby_id)

                case "start_game":
                    game_data = await lobby_manager.handle_start_game(user_id=user_id)
                    game_id, players = game_data
                    game_manager.create_game(game_id=game_id, players=players)
                    await lobby_manager.handle_disconnect_lobby(user_id=user_id)
                    break

    except WebSocketDisconnect as err:
        match err.code:
            case 1001 | 1012:
                await lobby_manager.handle_disconnect_lobby(user_id=user_id, error=True)
            case _:
                print(err)
                pass
