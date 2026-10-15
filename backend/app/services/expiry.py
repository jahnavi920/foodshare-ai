from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Donation, Pickup


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def expire_overdue(db: Session) -> int:
    """Expiry time dhaatina donations ni 'expired' ga mark chestundi. Marked count istundi."""
    now = utc_now()

    # Accept ayyi, inka pickup kaani donations: pickup cancel (capacity free avtundi)
    overdue_accepted = select(Donation.id).where(
        Donation.status == "accepted", Donation.expiry_at <= now)
    db.execute(update(Pickup)
               .where(Pickup.status == "assigned", Pickup.donation_id.in_(overdue_accepted))
               .values(status="expired")
               .execution_options(synchronize_session=False))

    result = db.execute(update(Donation)
                        .where(Donation.status.in_(["posted", "accepted"]),
                               Donation.expiry_at <= now)
                        .values(status="expired")
                        .execution_options(synchronize_session=False))
    db.commit()
    return result.rowcount