import getpass

from sqlalchemy import select

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

Base.metadata.create_all(bind=engine)

email = input("Admin email: ").strip().lower()
name = input("Admin name: ").strip() or "Admin"
password = getpass.getpass("Admin password (min 8 characters): ")
if len(password) < 8:
    raise SystemExit("Password must be at least 8 characters")

with SessionLocal() as db:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.role = "admin"
        user.password_hash = hash_password(password)
        print("Existing user promoted to admin.")
    else:
        db.add(User(name=name, email=email,
                    password_hash=hash_password(password), role="admin"))
        print("Admin created.")
    db.commit()