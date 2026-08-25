import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from fastapi.responses import JSONResponse

from src.connection.manager import ConnectionManager

from src.lobby.rules_txt import rules
from src.lobby.manager import LobbyManager
from src.lobby.enums import EventType
from src.lobby.errors import LobbyActionError
from src.game.manager import GameManager
from src.game.models import Game
from src.user.models import User
from src.protocol import lobby_message_adapter


router = APIRouter(
    prefix="",
    tags=["Lobby"]
)


connection_manager = ConnectionManager()
lobby_manager = LobbyManager(connection_manager)
game_manager = GameManager(connection_manager)
LOBBY_CAPABILITIES = ["kick_users", "lobby_configuration", "public_lobbies"]


@router.get("/check_lobby/{lobby_id}")
async def check_lobby(lobby_id: str):
    lobby = lobby_manager.lobbies.get(lobby_id)
    exists = lobby is not None and not lobby.in_game and not lobby.is_full
    message = "The lobby doesn't exist or no slots."
    return JSONResponse(content={"exists": exists, "msg": message})


@router.get("/public_lobbies")
async def get_public_lobbies():
    return JSONResponse(content=lobby_manager.get_public_lobbies())


@router.get("/rules")
async def get_rules():
    return JSONResponse(content={"rules": rules})


@router.websocket("/ws/lobby/{user_id}")
async def websocket_lobby(websocket: WebSocket, user_id: str):
    await connection_manager.connect(websocket=websocket)
    user = User(user_id=secrets.token_urlsafe(9), websocket=websocket, user_name=user_id)
    await connection_manager.send_message(
        websocket,
        {
            "type": EventType.SESSION.value,
            "user_id": user.user_id,
            "session_token": user.session_token,
            "capabilities": LOBBY_CAPABILITIES,
        },
    )

    try:
        while True:
            try:
                message = lobby_message_adapter.validate_python(await websocket.receive_json())
            except ValidationError:
                await connection_manager.send_message(
                    websocket,
                    {"type": EventType.SHOW_ERROR.value, "msg": "Invalid lobby message."},
                )
                continue

            data = message.model_dump()
            if "user_name" in data:
                user.user_name = data["user_name"].strip()

            match message.type:
                case EventType.CREATE_LOBBY.value:
                    await lobby_manager.handlers.handle_create_lobby(
                        user=user,
                        websocket=websocket,
                        is_public=data["is_public"],
                        max_players=data["max_players"],
                    )

                case EventType.CLOSE_LOBBY.value:
                    lobby = lobby_manager.get_lobby_by_user_id(user_id=user.user_id)
                    if lobby:
                        await lobby_manager.handlers.handle_disconnect_lobby(user_id=user.user_id)
                    break

                case EventType.JOIN_LOBBY.value:
                    lobby_id = data.get("lobby_id")
                    await lobby_manager.handlers.handle_join_lobby(user=user, websocket=websocket, lobby_id=lobby_id)

                case EventType.ADD_BOT.value:
                    try:
                        await lobby_manager.handlers.handle_add_bot(user_id=user.user_id)
                    except LobbyActionError as error:
                        await connection_manager.send_message(
                            websocket,
                            {"type": EventType.SHOW_ERROR.value, "msg": str(error)},
                        )

                case EventType.KICK_USER.value:
                    try:
                        await lobby_manager.handlers.handle_kick_user(
                            host_id=user.user_id,
                            target_id=data["user_id"],
                        )
                    except LobbyActionError as error:
                        await connection_manager.send_message(
                            websocket,
                            {"type": EventType.SHOW_ERROR.value, "msg": str(error)},
                        )

                case EventType.START_GAME.value:
                    game_data = await lobby_manager.handlers.handle_start_game(user_id=user.user_id)
                    if not game_data:
                        await connection_manager.send_message(
                            websocket,
                            {"type": EventType.SHOW_ERROR.value, "msg": "Only the host can start a full game."},
                        )
                        continue
                    game_id, players = game_data
                    game = Game(game_id=game_id, players=players, host_id=user.user_id)
                    game_manager.create_game(game=game)
                    await lobby_manager.handlers.handle_disconnect_lobby(user_id=user.user_id)
                    break

    except WebSocketDisconnect:
        if lobby_manager.get_lobby_by_user_id(user.user_id):
            await lobby_manager.handlers.handle_disconnect_lobby(user_id=user.user_id, error=True)
