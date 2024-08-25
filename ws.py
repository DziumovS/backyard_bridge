import random
from collections import deque

import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, tuple[WebSocket, str]] = {}
        self.clients_queue = deque()

    async def connect(self, websocket: WebSocket, client_id: int, player_name: str):
        await websocket.accept()
        self.active_connections[client_id] = (websocket, player_name)
        self.clients_queue.append(client_id)

    def disconnect(self, websocket: WebSocket):
        for client_id, (conn, _) in self.active_connections.items():
            if conn == websocket:
                del self.active_connections[client_id]
                self.clients_queue.remove(client_id)
                break

    async def send_personal_message(self, message: str, connection: tuple[WebSocket, str]):
        websocket = connection[0]
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection, _ in self.active_connections.values():
            await connection.send_text(message)

    def get_active_client_ids(self):
        return list(self.active_connections.keys())

    def get_player_name(self, client_id: int):
        """Получить имя игрока по его идентификатору."""
        return self.active_connections[client_id][1]

    async def update_start_button(self):
        """Активируем или деактивируем кнопку 'Start' в зависимости от количества подключенных игроков."""
        if 6 >= len(manager.clients_queue) >= 2:
            await self.broadcast("SYSTEM:ENABLE_START_BUTTON")
        else:
            await self.broadcast("SYSTEM:DISABLE_START_BUTTON")

    def set_player_name(self, client_id: int, websocket: WebSocket, data: str):
        player_name = data.split(":", 1)[1]
        self.active_connections[client_id] = (websocket, player_name)


class GameManager:
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager

    async def start_game(self):
        await self.shuffle_queue()
        await self.connection_manager.broadcast("SYSTEM:START_GAME")

        current_player_id = self.get_current_player()
        player_name = self.get_player_name(current_player_id)

        await self.notify_all_except_current(
            f"Game started! Player {player_name} goes first."
        )

        current_player_socket = self.connection_manager.active_connections[current_player_id]
        await self.connection_manager.send_personal_message(
            "Game started, it's your turn!", current_player_socket)

    async def shuffle_queue(self):
        """Определяем первого игрока."""
        clients = list(self.connection_manager.clients_queue)
        random_index = random.choice(range(len(clients)))
        first_player = clients.pop(random_index)
        self.connection_manager.clients_queue = deque([first_player] + clients)

    def rotate_queue(self):
        """Переход хода к следующему игроку."""
        self.connection_manager.clients_queue.rotate(-1)

    def get_current_player(self):
        """Получение текущего игрока (первого в очереди)."""
        return self.connection_manager.clients_queue[0]

    def get_player_name(self, client_id: int):
        """Получить имя игрока по его идентификатору."""
        return self.connection_manager.get_player_name(client_id)

    async def notify_all_except_current(self, message: str):
        """Уведомляем всех игроков, кроме текущего."""
        current_player_id = self.get_current_player()
        for player_id, connection in self.connection_manager.active_connections.items():
            if player_id != current_player_id:
                await self.connection_manager.send_personal_message(message, connection)

    async def process_player_turn(self, client_id: int, data: str):
        player_name = self.get_player_name(client_id)
        await self.connection_manager.broadcast(f"{player_name} says: {data}")

        self.rotate_queue()
        next_player_id = self.get_current_player()
        next_player_name = self.get_player_name(next_player_id)
        next_player_socket = self.connection_manager.active_connections[next_player_id]

        await self.connection_manager.broadcast(f"Next turn: {next_player_name}")
        await self.connection_manager.send_personal_message("It's your turn!", next_player_socket)


app = FastAPI()

manager = ConnectionManager()
game = GameManager(manager)

templates = Jinja2Templates(directory="frontend")


@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("ws.html", {"request": request})


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket, client_id=client_id, player_name=client_id)

    try:
        await manager.update_start_button()

        while True:
            data = await websocket.receive_text()

            match data:
                case _ if data.startswith("WS:"):
                    await game.start_game()

                case _ if data.startswith("NAME:"):
                    manager.set_player_name(client_id, websocket, data)
                    continue

                case _ if client_id == game.get_current_player():
                    await game.process_player_turn(client_id, data)

                case _:
                    await manager.send_personal_message("Please wait for your turn.", (websocket, ))

    except WebSocketDisconnect:
        current_player_id = game.get_current_player()
        player_name = manager.get_player_name(current_player_id)

        manager.disconnect(websocket)

        await manager.broadcast(f"{player_name} (#{current_player_id}) left the game")
        await manager.broadcast("SYSTEM:SHOW_START_BUTTON")
        await manager.update_start_button()
