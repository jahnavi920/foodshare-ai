from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Donation, User
from ..schemas import DonationCreate, DonationOut

router = APIRouter(prefix="/donations", tags=["donations"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


@router.post("", response_model=DonationOut, status_code=201)
def create_donation(data: DonationCreate,
                    user: User = Depends(require_roles("donor")),
                    db: Session = Depends(get_db)):
    expiry = to_utc_naive(data.expiry_at)
    if expiry <= utc_now():
        raise HTTPException(status_code=400, detail="expiry_at must be in the future")
    donation = Donation(
        donor_id=user.id,
        food_name=data.food_name,
        food_type=data.food_type,
        quantity=data.quantity,
        prepared_at=to_utc_naive(data.prepared_at),
        expiry_at=expiry,
        pickup_address=data.pickup_address,
        lat=data.lat,
        lng=data.lng,
    )
    db.add(donation)
    db.commit()
    db.refresh(donation)
    return donation


@router.get("/mine", response_model=list[DonationOut])
def my_donations(user: User = Depends(require_roles("donor")),
                 db: Session = Depends(get_db)):
    stmt = (select(Donation).where(Donation.donor_id == user.id)
            .order_by(Donation.created_at.desc()))
    return db.scalars(stmt).all()


@router.get("/available", response_model=list[DonationOut])
def available_donations(user: User = Depends(require_roles("ngo", "volunteer", "admin")),
                        db: Session = Depends(get_db)):
    stmt = (select(Donation)
            .where(Donation.status == "posted",
                                      Donation.verification_status.in_(["auto_approved", "admin_approved"]),
                   Donation.expiry_at > utc_now())
            .order_by(Donation.expiry_at.asc()))
    return db.scalars(stmt).all()


@router.get("", response_model=list[DonationOut])
def all_donations(user: User = Depends(require_roles("admin")),
                  db: Session = Depends(get_db)):
    return db.scalars(select(Donation).order_by(Donation.created_at.desc())).all()


@router.get("/{donation_id}", response_model=DonationOut)
def get_donation(donation_id: int,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found")
    if user.role == "donor" and donation.donor_id != user.id:
        raise HTTPException(status_code=403, detail="Not your donation")
    return donation