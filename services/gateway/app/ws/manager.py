"""WebSocket connection manager — one room per interview_id."""

from __future__ import annotations

import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, interview_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms.setdefault(interview_id, []).append(ws)
        logger.info("WS connected: room=%s total=%d", interview_id, len(self._rooms[interview_id]))

    def disconnect(self, interview_id: str, ws: WebSocket) -> None:
        room = self._rooms.get(interview_id, [])
        if ws in room:
            room.remove(ws)
        logger.info("WS disconnected: room=%s remaining=%d", interview_id, len(room))

    async def emit(self, interview_id: str, event: str, data: dict) -> None:
        """Broadcast an event to all listeners in the interview room."""
        dead: list[WebSocket] = []
        for ws in self._rooms.get(interview_id, []):
            try:
                await ws.send_json({"event": event, "data": data})
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(interview_id, ws)


manager = ConnectionManager()
