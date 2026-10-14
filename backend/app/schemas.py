from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

ALLOWED_SIGNUP_ROLES = {"donor", "ngo", "volunteer"}  # admin public signup ledu


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=64)
    role: str
    phone: str | None = None
    lat: float | None = None
    lng: float | None = None


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    phone: str | None = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class DonationCreate(BaseModel):
    food_name: str = Field(min_length=2, max_length=120)
    food_type: Literal["fruit", "vegetable", "bread", "cooked", "packaged"]
    quantity: int = Field(ge=1, le=10000)
    prepared_at: datetime | None = None
    expiry_at: datetime
    pickup_address: str = Field(min_length=3, max_length=255)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class DonationOut(BaseModel):
    id: int
    donor_id: int
    food_name: str
    food_type: str
    quantity: int
    prepared_at: datetime | None
    expiry_at: datetime
    pickup_address: str
    lat: float
    lng: float
    freshness_label: str | None
    freshness_confidence: float | None
    verification_status: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}