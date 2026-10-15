from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import NGO, Donation, Pickup, User
from ..services.matching import used_capacity

router = APIRouter(tags=["pickups"])

APPROVED = ("auto_approved", "admin_approved")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PickupOut(BaseModel):
    id: int
    donation_id: int
    ngo_id: int
    volunteer_id: int | None
    status: str
    assigned_at: datetime
    picked_up_at: datetime | None
    delivered_at: datetime | None
    food_name: str
    food_type: str
    quantity: int
    pickup_address: str
    lat: float
    lng: float
    expiry_at: datetime
    ngo_name: str
    ngo_address: str


def to_out(p: Pickup, d: Donation, n: NGO) -> PickupOut:
    return PickupOut(
        id=p.id, donation_id=p.donation_id, ngo_id=p.ngo_id,
        volunteer_id=p.volunteer_id, status=p.status,
        assigned_at=p.assigned_at, picked_up_at=p.picked_up_at,
        delivered_at=p.delivered_at, food_name=d.food_name,
        food_type=d.food_type, quantity=d.quantity,
        pickup_address=d.pickup_address, lat=d.lat, lng=d.lng,
        expiry_at=d.expiry_at, ngo_name=n.org_name, ngo_address=n.address)


def load(db: Session, pickup_id: int) -> tuple[Pickup, Donation, NGO]:
    p = db.get(Pickup, pickup_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Pickup not found")
    return p, db.get(Donation, p.donation_id), db.get(NGO, p.ngo_id)


def base_query():
    return (select(Pickup, Donation, NGO)
            .join(Donation, Donation.id == Pickup.donation_id)
            .join(NGO, NGO.id == Pickup.ngo_id))


@router.post("/donations/{donation_id}/accept", response_model=PickupOut, status_code=201)
def accept_donation(donation_id: int,
                    user: User = Depends(require_roles("ngo")),
                    db: Session = Depends(get_db)):
    ngo = db.scalar(select(NGO).where(NGO.user_id == user.id))
    if ngo is None:
        raise HTTPException(status_code=400, detail="Create your NGO profile first")
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found")
    if donation.verification_status not in APPROVED:
        raise HTTPException(status_code=400, detail="Donation has not passed the freshness check")
    if donation.expiry_at <= utc_now():
        raise HTTPException(status_code=400, detail="Donation has expired")
    accepted = [t.strip() for t in ngo.accepted_food_types.split(",")]
    if donation.food_type not in accepted:
        raise HTTPException(status_code=400, detail="Your NGO does not accept this food type")
    if ngo.capacity - used_capacity(db, ngo.id) < donation.quantity:
        raise HTTPException(status_code=400, detail="Not enough remaining capacity")

    # Atomic: modati NGO ki matrame dorukutundi
    result = db.execute(update(Donation)
                        .where(Donation.id == donation_id, Donation.status == "posted")
                        .values(status="accepted"))
    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="Donation was already taken")
    pickup = Pickup(donation_id=donation_id, ngo_id=ngo.id)
    db.add(pickup)
    db.commit()
    db.refresh(pickup)
    db.refresh(donation)
    return to_out(pickup, donation, ngo)


@router.get("/pickups/open", response_model=list[PickupOut])
def open_pickups(user: User = Depends(require_roles("volunteer", "admin")),
                 db: Session = Depends(get_db)):
    stmt = (base_query()
            .where(Pickup.status == "assigned", Pickup.volunteer_id.is_(None))
            .order_by(Donation.expiry_at.asc()))
    return [to_out(p, d, n) for p, d, n in db.execute(stmt).all()]


@router.get("/pickups/mine", response_model=list[PickupOut])
def my_pickups(user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    stmt = base_query().order_by(Pickup.assigned_at.desc())
    if user.role == "ngo":
        stmt = stmt.where(NGO.user_id == user.id)
    elif user.role == "volunteer":
        stmt = stmt.where(Pickup.volunteer_id == user.id)
    elif user.role == "donor":
        stmt = stmt.where(Donation.donor_id == user.id)
    return [to_out(p, d, n) for p, d, n in db.execute(stmt).all()]


@router.post("/pickups/{pickup_id}/claim", response_model=PickupOut)
def claim_pickup(pickup_id: int,
                 user: User = Depends(require_roles("volunteer")),
                 db: Session = Depends(get_db)):
    p, d, n = load(db, pickup_id)
    result = db.execute(update(Pickup)
                        .where(Pickup.id == pickup_id,
                               Pickup.status == "assigned",
                               Pickup.volunteer_id.is_(None))
                        .values(volunteer_id=user.id))
    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="Pickup already claimed or not available")
    db.commit()
    db.refresh(p)
    return to_out(p, d, n)


@router.post("/pickups/{pickup_id}/picked-up", response_model=PickupOut)
def mark_picked_up(pickup_id: int,
                   user: User = Depends(require_roles("volunteer")),
                   db: Session = Depends(get_db)):
    p, d, n = load(db, pickup_id)
    if p.volunteer_id != user.id:
        raise HTTPException(status_code=403, detail="Not your pickup")
    if p.status != "assigned":
        raise HTTPException(status_code=400, detail="Pickup is not waiting for collection")
    if d.expiry_at <= utc_now():
        raise HTTPException(status_code=400, detail="Food has expired and cannot be collected")
    p.status = "picked_up"
    p.picked_up_at = utc_now()
    d.status = "picked_up"
    db.commit()
    db.refresh(p)
    db.refresh(d)
    return to_out(p, d, n)


@router.post("/pickups/{pickup_id}/delivered", response_model=PickupOut)
def mark_delivered(pickup_id: int,
                   user: User = Depends(require_roles("volunteer")),
                   db: Session = Depends(get_db)):
    p, d, n = load(db, pickup_id)
    if p.volunteer_id != user.id:
        raise HTTPException(status_code=403, detail="Not your pickup")
    if p.status != "picked_up":
        raise HTTPException(status_code=400, detail="Food has not been picked up yet")
    p.status = "delivered"
    p.delivered_at = utc_now()
    d.status = "delivered"
    db.commit()
    db.refresh(p)
    db.refresh(d)
    return to_out(p, d, n)