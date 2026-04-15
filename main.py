import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from TikTokLive import TikTokLiveClient
from TikTokLive.events import GiftEvent, CommentEvent, LikeEvent, FollowEvent, ShareEvent
import uvicorn

app = FastAPI()

# Gestor de conexiones para el navegador
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{uniqueId}")
async def websocket_endpoint(websocket: WebSocket, uniqueId: str):
    await manager.connect(websocket)
    
    # Configuramos el cliente de TikTok
    client: TikTokLiveClient = TikTokLiveClient(uniqueId=f"@{uniqueId}")

    # --- EVENTOS DE TIKTOK ---

    @client.on(GiftEvent)
    async def on_gift(event: GiftEvent):
        # Si el regalo tiene combo (varias rosas), solo avisamos una vez o por cada una
        if event.gift.streakable and not event.gift.finished:
            return
        
        await manager.broadcast({
            "type": "gift",
            "gift": event.gift.info.name,  # Nombre técnico del sticker
            "user": event.user.nickname
        })

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        await manager.broadcast({
            "type": "comment",
            "text": event.comment,
            "user": event.user.nickname
        })

    @client.on(LikeEvent)
    async def on_like(event: LikeEvent):
        await manager.broadcast({
            "type": "like",
            "user": event.user.nickname,
            "count": event.like_count
        })

    @client.on(FollowEvent)
    async def on_follow(event: FollowEvent):
        await manager.broadcast({
            "type": "follow",
            "user": event.user.nickname
        })

    @client.on(ShareEvent)
    async def on_share(event: ShareEvent):
        await manager.broadcast({
            "type": "share",
            "user": event.user.nickname
        })

    # Ejecutar el cliente de TikTok en segundo plano
    try:
        asyncio.create_task(client.start())
        while True:
            # Mantener la conexión abierta
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await client.stop()
    except Exception as e:
        print(f"Error: {e}")
        await client.stop()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
