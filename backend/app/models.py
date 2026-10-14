from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # donor | ngo | volunteer | admin
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NGO(Base):
    __tablename__ = "ngos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    org_name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(String(255))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    capacity: Mapped[int] = mapped_column(default=100)  # meals per day
    accepted_food_types: Mapped[str] = mapped_column(
        String(200), default="fruit,vegetable,bread,cooked,packaged")


class Donation(Base):
    __tablename__ = "donations"

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    food_name: Mapped[str] = mapped_column(String(120))
    food_type: Mapped[str] = mapped_column(String(30))  # fruit | vegetable | bread | cooked | packaged
    quantity: Mapped[int] = mapped_column(default=1)  # servings
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expiry_at: Mapped[datetime] = mapped_column(DateTime)
    pickup_address: Mapped[str] = mapped_column(String(255))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # FreshCheck model output
    freshness_label: Mapped[str | None] = mapped_column(String(20), nullable=True)  # fresh | rotten
    freshness_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(20), default="pending")  # pending | auto_approved | manual_review | rejected

    status: Mapped[str] = mapped_column(
        String(20), default="posted")  # posted | matched | accepted | picked_up | delivered | expired
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Pickup(Base):
    __tablename__ = "pickups"

    id: Mapped[int] = mapped_column(primary_key=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donations.id"))
    ngo_id: Mapped[int] = mapped_column(ForeignKey("ngos.id"))
    volunteer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="assigned")  # assigned | picked_up | delivered
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)