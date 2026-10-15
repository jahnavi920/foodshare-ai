from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import Donation, User
from ..schemas_match import MatchOut
from ..services.matching import rank_ngos

router = APIRouter(prefix="/donations", tags=["matching"])


@router.get("/{donation_id}/matches", response_model=list[MatchOut])
def donation_matches(donation_id: int,
                     limit: int = 5,
                     user: User = Depends(require_roles("donor", "admin")),
                     db: Session = Depends(get_db)):
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found")
    if user.role == "donor" and donation.donor_id != user.id:
        raise HTTPException(status_code=403, detail="Not your donation")
    if donation.status != "posted":
        raise HTTPException(status_code=400, detail="Donation is no longer open for matching")
    if donation.verification_status != "auto_approved":
        raise HTTPException(status_code=400, detail="Donation has not passed the freshness check")
    return rank_ngos(db, donation, limit=min(max(limit, 1), 20))