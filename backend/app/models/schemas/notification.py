from typing import Optional
from pydantic import BaseModel


class DeviceTokenRegister(BaseModel):
    token: str
    platform: str = "ios"


class DeviceTokenResponse(BaseModel):
    id: int
    token: str
    platform: str
    active: bool

    class Config:
        from_attributes = True
