import asyncio

from fastapi import WebSocket

from src.user.models import User, Player
from src.bot.models import BotPlayer, BotUser


class Lobby:
    def __init__(self, lobby_id: str, host: User):
        self.lobby_id = lobby_id
        self.host = host
        self.in_game = False
        self.disconnect_lock = asyncio.Lock()
        self.users: dict[str, User] = {host.user_id: host}

    def is_host(self, user_id: str) -> bool:
        return self.host.user_id == user_id

    def add_user(self, user: User) -> None:
        self.users[user.user_id] = user

    def get_user(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def remove_user(self, user_id: str) -> None:
        if user_id in self.users:
            del self.users[user_id]

    def get_users(self) -> list[dict]:
        return [
            {"user_id": user.user_id, "user_name": user.user_name, "is_bot": user.is_bot}
            for user in self.users.values()
        ]

    def get_users_websocket(self) -> list[WebSocket]:
        return [user.websocket for user in self.users.values() if user.websocket is not None]

    def create_player_list(self) -> list[Player]:
        return [
            BotPlayer.from_user(user)
            if isinstance(user, BotUser)
            else Player(user.user_id, user.websocket, user.user_name, user.session_token)
            for user in self.users.values()
        ]
