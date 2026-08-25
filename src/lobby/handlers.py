from fastapi import WebSocket

from src.user.models import User
from src.lobby.enums import EventType
from src.lobby.models import Lobby
from src.lobby.errors import LobbyActionError



class LobbyHandlers:
    def __init__(self, lobby_manager):
        self.lobby_manager = lobby_manager
        self.connection_manager = lobby_manager.connection_manager

    async def update_start_button(self, lobby: Lobby) -> None:
        enable_start = len(lobby.users) == lobby.max_players
        await self.connection_manager.send_message(
            websocket=lobby.host.websocket,
            message={"type": EventType.TOGGLE_START_BUTTON.value, "enable": enable_start}
        )

    async def handle_create_lobby(
        self,
        user: User,
        websocket: WebSocket,
        *,
        is_public: bool = False,
        max_players: int = 4,
    ) -> None:
        lobby_id = self.lobby_manager.generate_lobby_id()
        lobby = Lobby(
            lobby_id=lobby_id,
            host=user,
            is_public=is_public,
            max_players=max_players,
        )
        self.lobby_manager.add_lobby(lobby)

        message = f"You have created {lobby.name}"

        await self.connection_manager.send_message(
            websocket=websocket,
            message={
                "type": EventType.LOBBY_CREATED.value,
                "lobby_id": lobby_id,
                "lobby_name": lobby.name,
                "is_public": lobby.is_public,
                "max_players": lobby.max_players,
                "msg": message,
            }
        )
        await self.connection_manager.send_message(
            websocket=websocket,
            message={
                "type": EventType.USERS_UPDATE.value,
                "users": lobby.get_users(),
                "is_host": True,
                "max_players": lobby.max_players,
            }
        )
        await self.update_start_button(lobby=lobby)

    async def handle_join_lobby(self, user: User, websocket: WebSocket, lobby_id: str) -> None:
        lobby = self.lobby_manager.get_lobby(lobby_id)
        if not lobby or lobby.in_game or lobby.is_full:
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
        message = f"You have joined {lobby.name}"
        await self.connection_manager.send_message(
            websocket=websocket,
            message={
                "type": EventType.JOINED_LOBBY.value,
                "lobby_id": lobby_id,
                "lobby_name": lobby.name,
                "is_public": lobby.is_public,
                "max_players": lobby.max_players,
                "users": lobby.get_users(),
                "msg": message}
        )
        await self.connection_manager.broadcast(
            websockets=lobby.get_users_websocket(),
            message={
                "type": EventType.USERS_UPDATE.value,
                "users": lobby.get_users(),
                "max_players": lobby.max_players,
            }
        )
        await self.update_start_button(lobby)

    async def handle_add_bot(self, user_id: str) -> None:
        lobby = self.lobby_manager.get_lobby_by_user_id(user_id)
        if not lobby or not lobby.is_host(user_id):
            raise LobbyActionError("Only the host can add a bot.")
        if lobby.in_game or lobby.is_full:
            raise LobbyActionError("The lobby is full.")

        bot = self.lobby_manager.bot_factory.create(
            existing_names={user.user_name for user in lobby.users.values()},
        )
        self.lobby_manager.add_user(lobby, bot)
        await self.connection_manager.broadcast(
            websockets=lobby.get_users_websocket(),
            message={
                "type": EventType.USERS_UPDATE.value,
                "users": lobby.get_users(),
                "max_players": lobby.max_players,
            },
        )
        await self.update_start_button(lobby)

    async def handle_kick_user(self, host_id: str, target_id: str) -> None:
        lobby = self.lobby_manager.get_lobby_by_user_id(host_id)
        if not lobby or not lobby.is_host(host_id):
            raise LobbyActionError("Only the host can remove players.")
        if lobby.in_game:
            raise LobbyActionError("Players cannot be removed after the game starts.")
        if target_id == host_id:
            raise LobbyActionError("The host cannot remove themselves.")

        async with lobby.disconnect_lock:
            target = lobby.get_user(target_id)
            if target is None:
                raise LobbyActionError("This player is no longer in the lobby.")

            self.lobby_manager.remove_user(lobby, target_id)
            if target.websocket is not None:
                await self.connection_manager.send_message(
                    target.websocket,
                    {
                        "type": EventType.KICKED_FROM_LOBBY.value,
                        "msg": "The host removed you from the lobby.",
                    },
                )
                await self.connection_manager.disconnect(target.websocket)

            await self.connection_manager.broadcast(
                websockets=lobby.get_users_websocket(),
                message={
                    "type": EventType.USERS_UPDATE.value,
                    "users": lobby.get_users(),
                    "max_players": lobby.max_players,
                },
            )
            await self.update_start_button(lobby)

    async def handle_start_game(self, user_id: str) -> tuple[str, list[User]]:
        lobby = self.lobby_manager.get_lobby_by_user_id(user_id)
        if (
            lobby
            and lobby.is_host(user_id)
            and len(lobby.users) == lobby.max_players
            and not lobby.in_game
        ):
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
                        websockets=[
                            remaining.websocket
                            for remaining in remaining_users
                            if remaining.websocket is not None
                        ],
                        message={"type": EventType.START_GAME.value, "lobby_id": lobby.lobby_id}
                        if lobby.in_game else {"type": EventType.LOBBY_CLOSED.value}
                    )
                    await self.connection_manager.disconnect(websocket=user.websocket, error=error)
                    for remaining in remaining_users:
                        if remaining.websocket is not None:
                            await self.connection_manager.disconnect(websocket=remaining.websocket)

                    self.lobby_manager.remove_lobby(lobby.lobby_id)
                else:
                    await self.connection_manager.broadcast(
                        websockets=lobby.get_users_websocket(),
                        message={
                            "type": EventType.USERS_UPDATE.value,
                            "users": lobby.get_users(),
                            "max_players": lobby.max_players,
                        }
                    )
                    await self.update_start_button(lobby)

                    await self.connection_manager.disconnect(websocket=user.websocket, error=error)
