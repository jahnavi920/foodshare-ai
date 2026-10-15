from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import NGO, Donation, Pickup, User
from ..services.expiry import expire_overdue
from ..services.matching import used_capacity

router = APIRouter(prefix="/admin", tags=["admin-stats"])

# Rough assumptions (estimate). Report lo cite cheyyadaniki nijamaina source tho marchu.
KG_PER_MEAL = 0.4
CO2E_PER_KG_FOOD = 2.5


@router.get("/stats")
def admin_stats(user: User = Depends(require_roles("admin")),
                db: Session = Depends(get_db)):
    expire_overdue(db)

    donations = db.scalars(select(Donation)).all()
    pickups = db.scalars(select(Pickup)).all()
    ngos = db.scalars(select(NGO)).all()
    users = db.scalars(select(User)).all()

    by_status = Counter(d.status for d in donations)
    by_verification = Counter(d.verification_status for d in donations)

    delivered = [d for d in donations if d.status == "delivered"]
    meals_delivered = sum(d.quantity for d in delivered)
    meals_in_progress = sum(d.quantity for d in donations
                            if d.status in ("accepted", "picked_up"))
    meals_expired = sum(d.quantity for d in donations if d.status == "expired")
    spoiled_blocked = sum(1 for d in donations
                          if d.verification_status in ("rejected", "admin_rejected"))

    minutes = [(p.delivered_at - p.assigned_at).total_seconds() / 60
               for p in pickups if p.status == "delivered" and p.delivered_at]
    avg_delivery_minutes = round(sum(minutes) / len(minutes), 1) if minutes else None

    names = {u.id: u.name for u in users}
    donor_totals = Counter()
    for d in delivered:
        donor_totals[d.donor_id] += d.quantity
    top_donors = [{"donor": names.get(i, f"User {i}"), "meals_delivered": q}
                  for i, q in donor_totals.most_common(5)]

    ngo_capacity = []
    for n in ngos:
        used = used_capacity(db, n.id)
        ngo_capacity.append({"ngo_id": n.id, "org_name": n.org_name,
                             "capacity": n.capacity, "in_use": used,
                             "remaining": max(n.capacity - used, 0)})

    kg_saved = meals_delivered * KG_PER_MEAL
    return {
        "donations": {
            "total": len(donations),
            "by_status": dict(by_status),
            "by_verification": dict(by_verification),
        },
        "impact": {
            "meals_delivered": meals_delivered,
            "meals_in_progress": meals_in_progress,
            "meals_expired": meals_expired,
            "avg_delivery_minutes": avg_delivery_minutes,
            "estimated_food_saved_kg": round(kg_saved, 1),
            "estimated_co2e_avoided_kg": round(kg_saved * CO2E_PER_KG_FOOD, 1),
            "estimate_note": f"Assumes {KG_PER_MEAL} kg per meal and {CO2E_PER_KG_FOOD} kg CO2e per kg of food",
        },
        "freshcheck": {
            "checked_by_ai": sum(1 for d in donations if d.freshness_label),
            "auto_approved": by_verification.get("auto_approved", 0),
            "spoiled_blocked": spoiled_blocked,
            "waiting_for_manual_review": by_verification.get("manual_review", 0),
            "approved_by_admin": by_verification.get("admin_approved", 0),
        },
        "people": {
            "donors": sum(1 for u in users if u.role == "donor"),
            "ngos": len(ngos),
            "volunteers": sum(1 for u in users if u.role == "volunteer"),
        },
        "top_donors": top_donors,
        "ngo_capacity": ngo_capacity,
    }