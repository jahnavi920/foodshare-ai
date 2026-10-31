"""Public endpoints: landing-page statistics and the forgot-password flow."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import NGO, Donation, User
from ..reset_model import PasswordReset
from ..security import hash_password

router = APIRouter(tags=["public"])

CODE_MINUTES = 15
KG_PER_MEAL = 0.4
CO2E_PER_KG = 2.5
# Demo mode: show the reset code on screen. Set SHOW_RESET_CODE=0 once real email is added.
SHOW_RESET_CODE = os.getenv("SHOW_RESET_CODE", "1") == "1"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_code(email: str, code: str) -> str:
    return hashlib.sha256(f"{email}:{code}".encode()).hexdigest()


# ---------- landing page stats (real numbers from the database) ----------
@router.get("/public/stats")
def public_stats(db: Session = Depends(get_db)):
    def count(stmt):
        return db.scalar(stmt) or 0

    delivered_meals = count(select(func.coalesce(func.sum(Donation.quantity), 0))
                            .where(Donation.status == "delivered"))
    return {
        "donations_posted": count(select(func.count(Donation.id))),
        "donations_delivered": count(select(func.count(Donation.id))
                                     .where(Donation.status == "delivered")),
        "meals_delivered": int(delivered_meals),
        "ngos": count(select(func.count(NGO.id))),
        "volunteers": count(select(func.count(User.id)).where(User.role == "volunteer")),
        "donors": count(select(func.count(User.id)).where(User.role == "donor")),
        "food_saved_kg": round(delivered_meals * KG_PER_MEAL, 1),
        "co2e_avoided_kg": round(delivered_meals * KG_PER_MEAL * CO2E_PER_KG, 1),
    }


# ---------- forgot password ----------
class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6, max_length=64)


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    message = "If that email is registered, a reset code has been created."
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        return {"message": message}

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.execute(delete(PasswordReset).where(PasswordReset.email == email))
    db.add(PasswordReset(email=email, code_hash=hash_code(email, code),
                         expires_at=utcnow() + timedelta(minutes=CODE_MINUTES)))
    db.commit()

    result = {"message": message, "expires_in_minutes": CODE_MINUTES}
    if SHOW_RESET_CODE:
        result["demo_code"] = code
    return result


@router.post("/auth/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    row = db.scalar(select(PasswordReset).where(PasswordReset.email == email))
    bad = HTTPException(status_code=400, detail="Invalid or expired reset code")
    if not row or row.expires_at < utcnow():
        raise bad
    if not secrets.compare_digest(row.code_hash, hash_code(email, body.code)):
        raise bad

    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise bad
    user.password_hash = hash_password(body.new_password)
    db.execute(delete(PasswordReset).where(PasswordReset.email == email))
    db.commit()
    return {"message": "Password updated. You can sign in now."}
