import asyncio

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class ConnectionManager:
    @staticmethod
    async def connect(websocket: WebSocket) -> None:
        await websocket.accept()

    @staticmethod
    async def disconnect(websocket: WebSocket, error: bool = False) -> bool:
        if error:
            return False
        try:
            await websocket.close(code=1000)
        except (RuntimeError, WebSocketDisconnect):
            return False
        return True

    @staticmethod
    async def send_message(websocket: WebSocket, message: dict) -> bool:
        try:
            await websocket.send_json(message)
        except (RuntimeError, WebSocketDisconnect):
            return False
        return True

    @staticmethod
    async def broadcast(websockets: list[WebSocket], message: dict) -> None:
        await asyncio.gather(*(
            ConnectionManager.send_message(websocket=websocket, message=message)
            for websocket in websockets
        ))
