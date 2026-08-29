from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import decode_access_token
from ..ws_manager import manager

router = APIRouter(tags=["ws"])


@router.websocket("/ws/groups/{group_id}")
async def group_ws(websocket: WebSocket, group_id: int, token: str = "", db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4401)
        return

    user_id = int(payload["sub"])
    member = (
        db.query(models.GroupMember)
        .filter(models.GroupMember.group_id == group_id, models.GroupMember.user_id == user_id)
        .first()
    )
    if member is None:
        await websocket.close(code=4403)
        return

    await manager.connect(group_id, websocket)
    try:
        while True:
            # Clients don't need to send anything; keep the connection alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(group_id, websocket)
