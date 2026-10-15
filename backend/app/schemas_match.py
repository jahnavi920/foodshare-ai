from typing import Literal

from pydantic import BaseModel, Field

FoodType = Literal["fruit", "vegetable", "bread", "cooked", "packaged"]
ALL_FOOD_TYPES = ["fruit", "vegetable", "bread", "cooked", "packaged"]


class NGOProfileIn(BaseModel):
    org_name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=3, max_length=255)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    capacity: int = Field(default=100, ge=1, le=100000)
    accepted_food_types: list[FoodType] = Field(default_factory=lambda: list(ALL_FOOD_TYPES))


class NGOOut(BaseModel):
    id: int
    org_name: str
    address: str
    lat: float
    lng: float
    capacity: int
    accepted_food_types: list[str]


class ScoreBreakdown(BaseModel):
    distance: float
    urgency: float
    capacity: float


class MatchOut(BaseModel):
    ngo_id: int
    org_name: str
    address: str
    distance_km: float
    travel_minutes: int
    remaining_capacity: int
    score: float
    breakdown: ScoreBreakdown