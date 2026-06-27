"""
Per-process WebSocket connection registry.

Knows only about sockets connected to *this* server instance. Cross-instance
delivery is handled by the Redis pub/sub bridge in `pubsub.py`, which calls
`send_local` on whichever instance actually holds the recipient's socket.
"""
import asyncio
import uuid
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> set of live sockets (a user may connect from multiple devices)
        self._local: dict[uuid.UUID, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def add(self, user_id: uuid.UUID, ws: WebSocket) -> bool:
        """Register a socket. Returns True if it is this user's FIRST socket
        on this instance (caller should then subscribe the Redis channel)."""
        async with self._lock:
            sockets = self._local.get(user_id)
            first = not sockets
            if sockets is None:
                sockets = set()
                self._local[user_id] = sockets
            sockets.add(ws)
            return first

    async def remove(self, user_id: uuid.UUID, ws: WebSocket) -> bool:
        """Deregister a socket. Returns True if it was this user's LAST socket
        on this instance (caller should then unsubscribe the Redis channel)."""
        async with self._lock:
            sockets = self._local.get(user_id)
            if not sockets:
                return False
            sockets.discard(ws)
            if not sockets:
                self._local.pop(user_id, None)
                return True
            return False

    def is_local(self, user_id: uuid.UUID) -> bool:
        return bool(self._local.get(user_id))

    async def send_local(self, user_id: uuid.UUID, payload: dict[str, Any]) -> None:
        """Deliver a JSON payload to all of this user's sockets on this instance."""
        sockets = list(self._local.get(user_id, set()))
        if not sockets:
            return
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.remove(user_id, ws)


# Module-level singleton shared across the app.
manager = ConnectionManager()
