import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from app.schemas import ClientServer
from app.connected_servers import connected_servers

router = APIRouter()

admin_connections: list[WebSocket] = []


@router.websocket("/ws/register")
async def ws_register(websocket: WebSocket):
    await websocket.accept()
    server: ClientServer | None = None
    try:
        # Ожидаем, что сервер отправит JSON с данными для регистрации
        data = await websocket.receive_json()
        server = ClientServer(**data)
        connected_servers.append(server)
        # После регистрации рассылаем обновление всем админ-клиентам
        await broadcast_servers()

        # Держим соединение открытым (например, для heartbeat)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if server and server in connected_servers:
            connected_servers.remove(server)
            await broadcast_servers()


@router.websocket("/ws/servers")
async def ws_servers(websocket: WebSocket):
    await websocket.accept()
    admin_connections.append(websocket)
    try:
        # Преобразуем список серверов с помощью jsonable_encoder
        data = jsonable_encoder([server.model_dump() for server in connected_servers])
        await websocket.send_json(data)
        while True:
            # Например, можно отправлять heartbeat каждые 5 секунд
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        admin_connections.remove(websocket)


async def broadcast_servers():
    """
    Отправляет всем подключённым админ-клиентам обновлённый список серверов.
    """
    data = [server.model_dump() for server in connected_servers]
    for connection in admin_connections:
        try:
            await connection.send_json(data)
        except Exception:
            pass  # Если отправка не удалась, можно обработать исключение