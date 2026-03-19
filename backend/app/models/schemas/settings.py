from pydantic import BaseModel
from typing import Optional


class UserProfileResponse(BaseModel):
    capital: float
    max_loss_per_trade: float
    accepts_options: bool
    accepts_margin: bool
    accepts_unlimited_risk: bool
    accepts_multi_leg: bool
    time_horizon: str
    experience_level: str
    risk_multiplier: float
    notifications_enabled: bool

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    capital: Optional[float] = None
    max_loss_per_trade: Optional[float] = None
    accepts_options: Optional[bool] = None
    accepts_margin: Optional[bool] = None
    accepts_unlimited_risk: Optional[bool] = None
    accepts_multi_leg: Optional[bool] = None
    time_horizon: Optional[str] = None
    experience_level: Optional[str] = None
    risk_multiplier: Optional[float] = None
    notifications_enabled: Optional[bool] = None
