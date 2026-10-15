from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Donation, User
from ..schemas import DonationOut

router = APIRouter(tags=["admin"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = (BACKEND_DIR / "uploads").resolve()
APPROVED = ("auto_approved", "admin_approved")


class ReviewIn(BaseModel):
    decision: Literal["approve", "reject"]


@router.get("/admin/review-queue", response_model=list[DonationOut])
def review_queue(user: User = Depends(require_roles("admin")),
                 db: Session = Depends(get_db)):
    stmt = (select(Donation)
            .where(Donation.verification_status == "manual_review")
            .order_by(Donation.expiry_at.asc()))
    return db.scalars(stmt).all()


@router.post("/admin/donations/{donation_id}/review", response_model=DonationOut)
def review_donation(donation_id: int, data: ReviewIn,
                    user: User = Depends(require_roles("admin")),
                    db: Session = Depends(get_db)):
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found")
    if donation.verification_status != "manual_review":
        raise HTTPException(status_code=400, detail="Donation is not waiting for review")
    if data.decision == "approve":
        donation.verification_status = "admin_approved"
    else:
        donation.verification_status = "admin_rejected"
        donation.status = "rejected"
    db.commit()
    db.refresh(donation)
    return donation


@router.get("/donations/{donation_id}/image")
def donation_image(donation_id: int,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    donation = db.get(Donation, donation_id)
    if donation is None or not donation.image_path:
        raise HTTPException(status_code=404, detail="Image not found")
    if user.role == "donor" and donation.donor_id != user.id:
        raise HTTPException(status_code=403, detail="Not your donation")
    if user.role in ("ngo", "volunteer") and donation.verification_status not in APPROVED:
        raise HTTPException(status_code=403, detail="Image not available")
    path = (BACKEND_DIR / donation.image_path).resolve()
    if path.parent != UPLOAD_DIR or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)