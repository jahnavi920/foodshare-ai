import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Donation, User
from ..schemas import DonationOut
from ..services.freshness import predict_image

router = APIRouter(tags=["freshcheck"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"  # backend/uploads
MAX_BYTES = 5 * 1024 * 1024
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

MESSAGES = {
    "auto_approved": "Fresh. Donation is now visible to NGOs.",
    "manual_review": "Sent for manual review before NGOs can see it.",
    "rejected": "Rejected: the item looks spoiled and is not safe to donate.",
}


class AIResult(BaseModel):
    label: str | None = None
    predicted_class: str | None = None
    confidence: float | None = None
    decision: str
    threshold: float | None = None
    top3: list[dict] | None = None
    note: str | None = None


class VerifyOut(BaseModel):
    donation: DonationOut
    ai: AIResult
    message: str


def read_image(file: UploadFile) -> bytes:
    if file.content_type not in EXTENSIONS:
        raise HTTPException(status_code=400, detail="Upload a JPG, PNG or WEBP image")
    data = file.file.read(MAX_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 5 MB or smaller")
    return data


@router.post("/predict", response_model=AIResult)
def predict(file: UploadFile = File(...),
            user: User = Depends(get_current_user)):
    """Quick test: photo upload chesthe verdict vastundi, database lo emi save avvadu."""
    data = read_image(file)
    try:
        return predict_image(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/donations/{donation_id}/verify", response_model=VerifyOut)
def verify_donation(donation_id: int,
                    file: UploadFile = File(...),
                    user: User = Depends(require_roles("donor")),
                    db: Session = Depends(get_db)):
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found")
    if donation.donor_id != user.id:
        raise HTTPException(status_code=403, detail="Not your donation")
    if donation.verification_status != "pending":
        raise HTTPException(status_code=400, detail="This donation has already been verified")

    data = read_image(file)

    if donation.food_type == "fruit":
        try:
            ai = predict_image(data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        donation.freshness_label = ai["label"]
        donation.freshness_confidence = ai["confidence"]
        decision = ai["decision"]
    else:
        decision = "manual_review"
        ai = {"decision": decision,
              "note": f"The AI model is trained on fruit only, so {donation.food_type} needs manual review."}

    UPLOAD_DIR.mkdir(exist_ok=True)
    filename = f"{uuid.uuid4().hex}{EXTENSIONS[file.content_type]}"
    (UPLOAD_DIR / filename).write_bytes(data)
    donation.image_path = f"uploads/{filename}"

    donation.verification_status = decision
    if decision == "rejected":
        donation.status = "rejected"
    db.commit()
    db.refresh(donation)

    return {"donation": donation, "ai": ai, "message": MESSAGES[decision]}