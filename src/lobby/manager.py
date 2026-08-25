import secrets

from src.connection.manager import ConnectionManager
from src.lobby.models import Lobby
from src.lobby.handlers import LobbyHandlers
from src.user.models import User
from src.bot.factory import BotFactory


class LobbyManager:
    def __init__(self, manager: ConnectionManager):
        self.connection_manager = manager
        self.lobbies: dict[str, Lobby] = {}
        self._lobby_ids_by_user: dict[str, str] = {}
        self.bot_factory = BotFactory()
        self.handlers = LobbyHandlers(self)

    def generate_lobby_id(self) -> str:
        while True:
            lobby_id = str(secrets.token_hex(3))
            if lobby_id not in self.lobbies:
                return lobby_id

    def get_lobby(self, lobby_id: str) -> Lobby | None:
        return self.lobbies.get(lobby_id)

    def get_public_lobbies(self) -> list[dict]:
        return [
            lobby.get_summary()
            for lobby in self.lobbies.values()
            if lobby.is_public and not lobby.in_game and not lobby.is_full
        ]

    def add_lobby(self, lobby: Lobby) -> None:
        self.lobbies[lobby.lobby_id] = lobby
        for user_id in lobby.users:
            self._lobby_ids_by_user[user_id] = lobby.lobby_id

    def remove_lobby(self, lobby_id: str) -> None:
        lobby = self.lobbies.pop(lobby_id, None)
        if lobby:
            for user_id in lobby.users:
                self._lobby_ids_by_user.pop(user_id, None)

    def add_user(self, lobby: Lobby, user: User) -> None:
        lobby.add_user(user)
        self._lobby_ids_by_user[user.user_id] = lobby.lobby_id

    def remove_user(self, lobby: Lobby, user_id: str) -> None:
        lobby.remove_user(user_id)
        self._lobby_ids_by_user.pop(user_id, None)

    def clear(self) -> None:
        self.lobbies.clear()
        self._lobby_ids_by_user.clear()

    def get_lobby_by_user_id(self, user_id: str) -> Lobby | None:
        lobby_id = self._lobby_ids_by_user.get(user_id)
        return self.lobbies.get(lobby_id) if lobby_id else None
