import uuid

from pydantic import BaseModel


class SaveResponse(BaseModel):
    post_id: uuid.UUID
    is_saved: bool
