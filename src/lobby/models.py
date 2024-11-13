from fastapi import WebSocket

from src.user.models import User, Player


class Lobby:
    def __init__(self, lobby_id: str, host: User):
        self.lobby_id = lobby_id
        self.host = host
        self.in_game = False
        self.users: dict[str, User] = {host.user_id: host}

    def __del__(self):
        print(f"Lobby '{self.lobby_id}' has been deleted.")

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
        return [{"user_id": user.user_id, "user_name": user.user_name} for user in self.users.values()]

    def get_users_websocket(self) -> list[WebSocket]:
        return [user.websocket for user in self.users.values()]

    def create_player_list(self) -> list[Player]:
        return [Player(user.user_id, user.websocket, user.user_name) for user in self.users.values()]
