from typing import Tuple, List

from fastapi import WebSocket

from src.user.models import User
from src.lobby.models import Lobby



class LobbyHandlers:
    def __init__(self, lobby_manager):
        self.lobby_manager = lobby_manager
        self.connection_manager = lobby_manager.connection_manager

    async def update_start_button(self, lobby: Lobby):
        num_users = len(lobby.users)
        enable_start = 2 <= num_users <= 4
        await self.connection_manager.send_message(
            websocket=lobby.host.websocket,
            message={"type": "toggle_start_button", "enable": enable_start}
        )

    async def handle_create_lobby(self, user: User, websocket: WebSocket):
        lobby_id = self.lobby_manager.generate_lobby_id()
        lobby = Lobby(lobby_id=lobby_id, host=user)
        self.lobby_manager.lobbies[lobby_id] = lobby

        message = f"You have created a lobby with ID: <b>{lobby_id}</b>"

        await self.connection_manager.send_message(
            websocket=websocket,
            message={"type": "lobby_created", "lobby_id": lobby_id, "msg": message}
        )
        await self.connection_manager.send_message(
            websocket=websocket,
            message={"type": "users_update", "users": lobby.get_users(), "is_host": True}
        )
        await self.update_start_button(lobby=lobby)

    async def handle_join_lobby(self, user: User, websocket: WebSocket, lobby_id: str):
        lobby = self.lobby_manager.get_lobby(lobby_id)
        if lobby:
            lobby.add_user(user)
            message = f"You have joined the lobby with ID: <b>{lobby_id}</b>"
            await self.connection_manager.send_message(
                websocket=websocket,
                message={"type": "joined_lobby", "lobby_id": lobby_id, "users": lobby.get_users(), "msg": message}
            )
            await self.connection_manager.broadcast(
                websockets=lobby.get_users_websocket(),
                message={"type": "users_update", "users": lobby.get_users()}
            )
            await self.update_start_button(lobby)

    async def handle_start_game(self, user_id: str) -> Tuple[str, List[User]]:
        lobby = self.lobby_manager.get_lobby_by_user_id(user_id)
        if lobby:
            lobby.in_game = True
            return lobby.lobby_id, lobby.create_player_list()

    async def handle_disconnect_lobby(self, user_id: str, error: bool = False):
        lobby = self.lobby_manager.get_lobby_by_user_id(user_id)
        if lobby:
            user = lobby.get_user(user_id=user_id)
            lobby.remove_user(user_id)
            if lobby.is_host(user_id):
                await self.connection_manager.broadcast(
                    websockets=lobby.get_users_websocket(),
                    message={"type": "start_game", "lobby_id": lobby.lobby_id}
                    if lobby.in_game else {"type": "lobby_closed"}
                )
                await self.connection_manager.disconnect(websocket=user.websocket, error=error)
                for user in lobby.users.values():
                    await self.connection_manager.disconnect(websocket=user.websocket)

                del self.lobby_manager.lobbies[lobby.lobby_id]
            else:
                await self.connection_manager.broadcast(
                    websockets=lobby.get_users_websocket(),
                    message={"type": "users_update", "users": lobby.get_users()}
                )
                await self.update_start_button(lobby)

                await self.connection_manager.disconnect(websocket=user.websocket, error=error)