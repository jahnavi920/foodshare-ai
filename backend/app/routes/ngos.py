from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import NGO, User
from ..schemas_match import NGOOut, NGOProfileIn

router = APIRouter(prefix="/ngos", tags=["ngos"])


def to_out(ngo: NGO) -> NGOOut:
    return NGOOut(
        id=ngo.id, org_name=ngo.org_name, address=ngo.address,
        lat=ngo.lat, lng=ngo.lng, capacity=ngo.capacity,
        accepted_food_types=[t.strip() for t in ngo.accepted_food_types.split(",") if t.strip()],
    )


@router.put("/me", response_model=NGOOut)
def save_my_profile(data: NGOProfileIn,
                    user: User = Depends(require_roles("ngo")),
                    db: Session = Depends(get_db)):
    if not data.accepted_food_types:
        raise HTTPException(status_code=400, detail="Select at least one food type")
    ngo = db.scalar(select(NGO).where(NGO.user_id == user.id))
    if ngo is None:
        ngo = NGO(user_id=user.id)
        db.add(ngo)
    ngo.org_name = data.org_name
    ngo.address = data.address
    ngo.lat = data.lat
    ngo.lng = data.lng
    ngo.capacity = data.capacity
    ngo.accepted_food_types = ",".join(data.accepted_food_types)
    db.commit()
    db.refresh(ngo)
    return to_out(ngo)


@router.get("/me", response_model=NGOOut)
def my_profile(user: User = Depends(require_roles("ngo")),
               db: Session = Depends(get_db)):
    ngo = db.scalar(select(NGO).where(NGO.user_id == user.id))
    if ngo is None:
        raise HTTPException(status_code=404, detail="Create your NGO profile first")
    return to_out(ngo)


@router.get("", response_model=list[NGOOut])
def list_ngos(user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    return [to_out(n) for n in db.scalars(select(NGO).order_by(NGO.org_name)).all()]