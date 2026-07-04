"""
Redis pub/sub bridge for cross-instance WebSocket fan-out.

Channel scheme: one channel per user, ``ws:user:{user_id}``.

Each server instance subscribes ONLY to the channels of users currently
connected to it (a bounded, naturally-sharded set) and runs a single background
reader that forwards anything received on those channels to the local
ConnectionManager. To send a message, the sending instance publishes the JSON
envelope to each recipient's channel; Redis fans it out to whichever instance
holds that recipient's socket.

Durability note: Redis pub/sub is fire-and-forget. Postgres is the source of
truth — on reconnect the client refetches history, so a missed live frame is
never a lost message.
"""

import asyncio
import json
import logging
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.core.config.settings import settings
from app.core.websocket.manager import manager

logger = logging.getLogger(__name__)

# A control channel we always stay subscribed to, so the pubsub connection is
# live even when no users are connected (avoids "reader with zero channels").
_CONTROL_CHANNEL = "ws:_control"

PRESENCE_ONLINE_SET = "presence:online"
_PRESENCE_TTL_SECONDS = 60


def _user_channel(user_id: uuid.UUID | str) -> str:
    return f"ws:user:{user_id}"


class ChatPubSub:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._pubsub: Any = None
        self._reader_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._running = False

    @property
    def redis(self) -> aioredis.Redis:
        if self._redis is None:
            raise RuntimeError("ChatPubSub not started")
        return self._redis

    async def start(self) -> None:
        """Open the Redis connection and start the background reader loop."""
        if self._running:
            return
        self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(_CONTROL_CHANNEL)
        self._running = True
        self._reader_task = asyncio.create_task(
            self._reader(), name="chat-pubsub-reader"
        )
        logger.info("ChatPubSub started (redis=%s)", settings.REDIS_URL)

    async def stop(self) -> None:
        self._running = False
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        try:
            if self._pubsub is not None:
                await self._pubsub.unsubscribe()
                await self._pubsub.aclose()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass
        try:
            if self._redis is not None:
                await self._redis.aclose()
        except Exception:  # pragma: no cover
            pass
        self._pubsub = None
        self._redis = None
        logger.info("ChatPubSub stopped")

    # --- Subscription management (called by the WS router on connect/disconnect) ---

    async def subscribe_user(self, user_id: uuid.UUID) -> None:
        async with self._lock:
            if self._pubsub is not None:
                await self._pubsub.subscribe(_user_channel(user_id))

    async def unsubscribe_user(self, user_id: uuid.UUID) -> None:
        async with self._lock:
            if self._pubsub is not None:
                await self._pubsub.unsubscribe(_user_channel(user_id))

    # --- Publishing (called from the send path / WS router) ---

    async def publish_to_user(
        self, user_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        if self._redis is None:
            logger.warning("publish_to_user called before ChatPubSub started")
            return
        await self._redis.publish(
            _user_channel(user_id), json.dumps(payload, default=str)
        )

    async def publish_to_users(
        self, user_ids: list[uuid.UUID], payload: dict[str, Any]
    ) -> None:
        for uid in user_ids:
            await self.publish_to_user(uid, payload)

    # --- Presence (best-effort, ephemeral) ---

    async def mark_online(self, user_id: uuid.UUID) -> None:
        if self._redis is None:
            return
        await self._redis.sadd(PRESENCE_ONLINE_SET, str(user_id))
        await self._redis.set(f"presence:user:{user_id}", "1", ex=_PRESENCE_TTL_SECONDS)

    async def refresh_presence(self, user_id: uuid.UUID) -> None:
        if self._redis is None:
            return
        await self._redis.set(f"presence:user:{user_id}", "1", ex=_PRESENCE_TTL_SECONDS)

    async def mark_offline(self, user_id: uuid.UUID) -> None:
        if self._redis is None:
            return
        await self._redis.srem(PRESENCE_ONLINE_SET, str(user_id))
        await self._redis.delete(f"presence:user:{user_id}")

    async def is_online(self, user_id: uuid.UUID) -> bool:
        if self._redis is None:
            return manager.is_local(user_id)
        return bool(await self._redis.sismember(PRESENCE_ONLINE_SET, str(user_id)))

    # --- Background reader: Redis -> local sockets ---

    async def _reader(self) -> None:
        assert self._pubsub is not None
        while self._running:
            try:
                msg = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg is None:
                    continue
                channel = msg.get("channel")
                data = msg.get("data")
                if not channel or channel == _CONTROL_CHANNEL or data is None:
                    continue
                # channel == "ws:user:{user_id}"
                try:
                    user_id = uuid.UUID(channel.rsplit(":", 1)[-1])
                except ValueError:
                    continue
                if not manager.is_local(user_id):
                    continue
                try:
                    payload = json.loads(data)
                except (TypeError, ValueError):
                    continue
                await manager.send_local(user_id, payload)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - keep the loop alive
                logger.exception("ChatPubSub reader error; continuing")
                await asyncio.sleep(0.5)


# Module-level singleton shared across the app.
pubsub = ChatPubSub()
