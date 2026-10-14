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