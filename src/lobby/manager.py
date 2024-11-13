import secrets

from src.connection.manager import ConnectionManager
from src.lobby.models import Lobby
from src.lobby.handlers import LobbyHandlers


class LobbyManager:
    def __init__(self, manager: ConnectionManager):
        self.connection_manager = manager
        self.lobbies: dict[str, Lobby] = {}
        self.handlers = LobbyHandlers(self)

    def generate_lobby_id(self) -> str:
        while True:
            lobby_id = str(secrets.token_hex(3))
            if lobby_id not in self.lobbies:
                return lobby_id

    def get_lobby(self, lobby_id: str) -> Lobby | None:
        return self.lobbies.get(lobby_id)

    def get_lobby_by_user_id(self, user_id: str) -> Lobby | None:
        for lobby in self.lobbies.values():
            if user_id in lobby.users:
                return lobby
        return None
