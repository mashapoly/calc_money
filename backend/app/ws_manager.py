import json
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Keeps track of active WebSocket connections per group and broadcasts events."""

    def __init__(self):
        self.active: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, group_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active[group_id].add(websocket)

    def disconnect(self, group_id: int, websocket: WebSocket):
        self.active[group_id].discard(websocket)
        if not self.active[group_id]:
            self.active.pop(group_id, None)

    async def broadcast(self, group_id: int, event: str, payload: dict):
        message = json.dumps({"event": event, "payload": payload}, default=str)
        dead = []
        for connection in self.active.get(group_id, set()):
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(group_id, connection)


manager = ConnectionManager()
