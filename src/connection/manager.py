from fastapi import WebSocket


class ConnectionManager:
    @staticmethod
    async def connect(websocket: WebSocket) -> None:
        await websocket.accept()

    @staticmethod
    async def disconnect(websocket: WebSocket, error: bool = False) -> None:
        if not error:
            await websocket.close(code=1000)

    @staticmethod
    async def send_message(websocket: WebSocket, message: dict) -> None:
        await websocket.send_json(message)

    @staticmethod
    async def broadcast(websockets: list[WebSocket], message: dict) -> None:
        for ws in websockets:
            await ConnectionManager.send_message(websocket=ws, message=message)
