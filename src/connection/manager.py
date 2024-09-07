from typing import List, Dict

from fastapi import WebSocket


class ConnectionManager:
    @staticmethod
    async def connect(websocket: WebSocket):
        await websocket.accept()

    @staticmethod
    async def disconnect(websocket: WebSocket, error: bool = False):
        if not error:
            await websocket.close(code=1000)

    @staticmethod
    async def send_message(websocket: WebSocket, message: Dict):
        await websocket.send_json(message)

    @staticmethod
    async def broadcast(websockets: List[WebSocket], message: Dict):
        for ws in websockets:
            await ConnectionManager.send_message(websocket=ws, message=message)
