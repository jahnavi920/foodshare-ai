import math
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import NGO, Donation, Pickup

AVG_SPEED_KMH = 25.0      # city lo average travel speed
MAX_DISTANCE_KM = 30.0    # idi kante dooram unte consider cheyyamu
WEIGHTS = {"distance": 0.4, "urgency": 0.3, "capacity": 0.3}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def used_capacity(db: Session, ngo_id: int) -> int:
    stmt = (select(func.coalesce(func.sum(Donation.quantity), 0))
            .select_from(Donation)
            .join(Pickup, Pickup.donation_id == Donation.id)
            .where(Pickup.ngo_id == ngo_id,
                   Pickup.status.in_(["assigned", "picked_up"])))
    return int(db.scalar(stmt) or 0)


def rank_ngos(db: Session, donation: Donation, limit: int = 5) -> list[dict]:
    hours_left = (donation.expiry_at - utc_now()).total_seconds() / 3600
    if hours_left <= 0:
        return []

    results = []
    for ngo in db.scalars(select(NGO)).all():
        # 1. Food type fit (hard filter)
        accepted = [t.strip() for t in ngo.accepted_food_types.split(",")]
        if donation.food_type not in accepted:
            continue

        # 2. Distance (hard filter)
        distance = haversine_km(donation.lat, donation.lng, ngo.lat, ngo.lng)
        if distance > MAX_DISTANCE_KM:
            continue

        # 3. Urgency: expiry ki mundu cherukovadam possible aa
        travel_hours = distance / AVG_SPEED_KMH
        if travel_hours >= hours_left * 0.8:
            continue

        # 4. Capacity: migilina capacity
        remaining = ngo.capacity - used_capacity(db, ngo.id)
        if remaining <= 0:
            continue

        distance_score = 1 - distance / MAX_DISTANCE_KM
        urgency_score = 1 - travel_hours / hours_left
        capacity_score = min(1.0, remaining / donation.quantity)
        total = (WEIGHTS["distance"] * distance_score
                 + WEIGHTS["urgency"] * urgency_score
                 + WEIGHTS["capacity"] * capacity_score)

        results.append({
            "ngo_id": ngo.id,
            "org_name": ngo.org_name,
            "address": ngo.address,
            "distance_km": round(distance, 2),
            "travel_minutes": round(travel_hours * 60),
            "remaining_capacity": remaining,
            "score": round(total, 3),
            "breakdown": {
                "distance": round(distance_score, 3),
                "urgency": round(urgency_score, 3),
                "capacity": round(capacity_score, 3),
            },
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]