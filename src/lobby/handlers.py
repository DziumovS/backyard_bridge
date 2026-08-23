from fastapi import WebSocket

from src.user.models import User
from src.lobby.enums import EventType
from src.lobby.models import Lobby



class LobbyHandlers:
    def __init__(self, lobby_manager):
        self.lobby_manager = lobby_manager
        self.connection_manager = lobby_manager.connection_manager

    async def update_start_button(self, lobby: Lobby) -> None:
        num_users = len(lobby.users)
        enable_start = 2 <= num_users <= 4
        await self.connection_manager.send_message(
            websocket=lobby.host.websocket,
            message={"type": EventType.TOGGLE_START_BUTTON.value, "enable": enable_start}
        )

    async def handle_create_lobby(self, user: User, websocket: WebSocket) -> None:
        lobby_id = self.lobby_manager.generate_lobby_id()
        lobby = Lobby(lobby_id=lobby_id, host=user)
        self.lobby_manager.add_lobby(lobby)

        message = f"You have created a lobby with ID: <b>{lobby_id}</b>"

        await self.connection_manager.send_message(
            websocket=websocket,
            message={"type": EventType.LOBBY_CREATED.value, "lobby_id": lobby_id, "msg": message}
        )
        await self.connection_manager.send_message(
            websocket=websocket,
            message={"type": EventType.USERS_UPDATE.value, "users": lobby.get_users(), "is_host": True}
        )
        await self.update_start_button(lobby=lobby)

    async def handle_join_lobby(self, user: User, websocket: WebSocket, lobby_id: str) -> None:
        lobby = self.lobby_manager.get_lobby(lobby_id)
        if not lobby or lobby.in_game or len(lobby.users) >= 4:
            await self.connection_manager.send_message(
                websocket=websocket,
                message={"type": EventType.SHOW_ERROR.value, "msg": "The lobby doesn't exist or no slots."},
            )
            return
        if user.user_id in lobby.users:
            await self.connection_manager.send_message(
                websocket=websocket,
                message={"type": EventType.SHOW_ERROR.value, "msg": "This player is already in the lobby."},
            )
            return

        self.lobby_manager.add_user(lobby, user)
        message = f"You have joined the lobby with ID: <b>{lobby_id}</b>"
        await self.connection_manager.send_message(
            websocket=websocket,
            message={
                "type": EventType.JOINED_LOBBY.value,
                "lobby_id": lobby_id,
                "users": lobby.get_users(),
                "msg": message}
        )
        await self.connection_manager.broadcast(
            websockets=lobby.get_users_websocket(),
            message={"type": EventType.USERS_UPDATE.value, "users": lobby.get_users()}
        )
        await self.update_start_button(lobby)

    async def handle_start_game(self, user_id: str) -> tuple[str, list[User]]:
        lobby = self.lobby_manager.get_lobby_by_user_id(user_id)
        if lobby and lobby.is_host(user_id) and 2 <= len(lobby.users) <= 4 and not lobby.in_game:
            lobby.in_game = True
            return lobby.lobby_id, lobby.create_player_list()

    async def handle_disconnect_lobby(self, user_id: str, error: bool = False) -> None:
        lobby = self.lobby_manager.get_lobby_by_user_id(user_id)
        if lobby:
            async with lobby.disconnect_lock:
                if self.lobby_manager.get_lobby(lobby.lobby_id) is not lobby:
                    return
                user = lobby.get_user(user_id=user_id)
                if user is None:
                    return
                self.lobby_manager.remove_user(lobby, user_id)
                if lobby.is_host(user_id):
                    remaining_users = list(lobby.users.values())
                    await self.connection_manager.broadcast(
                        websockets=[remaining.websocket for remaining in remaining_users],
                        message={"type": EventType.START_GAME.value, "lobby_id": lobby.lobby_id}
                        if lobby.in_game else {"type": EventType.LOBBY_CLOSED.value}
                    )
                    await self.connection_manager.disconnect(websocket=user.websocket, error=error)
                    for remaining in remaining_users:
                        await self.connection_manager.disconnect(websocket=remaining.websocket)

                    self.lobby_manager.remove_lobby(lobby.lobby_id)
                else:
                    await self.connection_manager.broadcast(
                        websockets=lobby.get_users_websocket(),
                        message={"type": EventType.USERS_UPDATE.value, "users": lobby.get_users()}
                    )
                    await self.update_start_button(lobby)

                    await self.connection_manager.disconnect(websocket=user.websocket, error=error)
