from typing import Literal

from pydantic import BaseModel, Field


class RegisterDeviceRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=512)
    platform: Literal["android", "ios"] = "android"


class DeviceResponse(BaseModel):
    token: str
    platform: str
    registered: bool = True
