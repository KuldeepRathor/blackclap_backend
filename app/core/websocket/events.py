"""
Shared WebSocket event envelope constants + builders.

Every frame on the wire is a JSON object of the shape::

    {"type": "<event>", "data": {...}}

Both the server (publishing) and the realtime router (parsing inbound frames)
use these helpers so the contract stays in one place. The Flutter client mirrors
these `type` strings in lib/models/chat_socket_event.dart.
"""
from typing import Any

# Server -> client
EVENT_MESSAGE_NEW = "message.new"
EVENT_MESSAGE_READ = "message.read"
EVENT_TYPING = "typing"
EVENT_PRESENCE = "presence"
EVENT_PONG = "pong"

# Client -> server
EVENT_PING = "ping"
# (clients may also send EVENT_TYPING / EVENT_MESSAGE_READ)


def envelope(event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": event_type, "data": data or {}}


def message_new(message: dict[str, Any]) -> dict[str, Any]:
    """`message` is a serialized MessageResponse (jsonable dict)."""
    return envelope(EVENT_MESSAGE_NEW, {"message": message})


def message_read(
    conversation_id: str,
    reader_id: str,
    last_read_message_id: str | None,
    read_at: str | None,
) -> dict[str, Any]:
    return envelope(
        EVENT_MESSAGE_READ,
        {
            "conversation_id": conversation_id,
            "reader_id": reader_id,
            "last_read_message_id": last_read_message_id,
            "read_at": read_at,
        },
    )


def typing(conversation_id: str, user_id: str, is_typing: bool) -> dict[str, Any]:
    return envelope(
        EVENT_TYPING,
        {"conversation_id": conversation_id, "user_id": user_id, "is_typing": is_typing},
    )


def presence(user_id: str, online: bool, last_seen: str | None = None) -> dict[str, Any]:
    return envelope(
        EVENT_PRESENCE,
        {"user_id": user_id, "online": online, "last_seen": last_seen},
    )


def pong() -> dict[str, Any]:
    return envelope(EVENT_PONG)
