import asyncio

from fastapi import WebSocket

from src.user.models import User, Player
from src.bot.models import BotPlayer, BotUser


class Lobby:
    def __init__(
        self,
        lobby_id: str,
        host: User,
        *,
        is_public: bool = False,
        max_players: int = 4,
    ):
        if not 2 <= max_players <= 4:
            raise ValueError("Lobby size must be between 2 and 4 players.")
        self.lobby_id = lobby_id
        self.host = host
        self.name = f"{host.user_name}'s lobby"
        self.is_public = is_public
        self.max_players = max_players
        self.in_game = False
        self.disconnect_lock = asyncio.Lock()
        self.users: dict[str, User] = {host.user_id: host}

    def is_host(self, user_id: str) -> bool:
        return self.host.user_id == user_id

    def add_user(self, user: User) -> None:
        self.users[user.user_id] = user

    @property
    def is_full(self) -> bool:
        return len(self.users) >= self.max_players

    def get_summary(self) -> dict:
        return {
            "lobby_id": self.lobby_id,
            "name": self.name,
            "players": len(self.users),
            "max_players": self.max_players,
        }

    def get_listing_summary(self) -> dict:
        summary = {
            "name": self.name,
            "players": len(self.users),
            "max_players": self.max_players,
            "is_private": not self.is_public,
        }
        if self.is_public:
            summary["lobby_id"] = self.lobby_id
        return summary

    def get_user(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def remove_user(self, user_id: str) -> None:
        if user_id in self.users:
            del self.users[user_id]

    def get_users(self) -> list[dict]:
        return [
            {
                "user_id": user.user_id,
                "user_name": user.user_name,
                "is_bot": user.is_bot,
                "is_host": self.is_host(user.user_id),
            }
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
