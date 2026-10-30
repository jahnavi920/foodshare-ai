import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .database import Base, SessionLocal, engine
from . import models  # noqa: F401  (tables register avvadaniki)
from .models import User
from .routes import admin, auth, donations, matching, ngos, pickups, stats, verify
from .security import hash_password
from .services.expiry import expire_overdue

Base.metadata.create_all(bind=engine)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def seed_admin() -> None:
    """Deploy kosam: ADMIN_EMAIL and ADMIN_PASSWORD set chesthe admin create avtundi."""
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or len(password) < 8:
        return
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            return
        db.add(User(name="Admin", email=email,
                    password_hash=hash_password(password), role="admin"))
        db.commit()


def run_expiry() -> None:
    with SessionLocal() as db:
        expire_overdue(db)


async def expiry_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(run_expiry)
        except Exception as exc:  # noqa: BLE001
            print("Expiry job failed:", exc)
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_admin()
    task = asyncio.create_task(expiry_loop())
    yield
    task.cancel()


app = FastAPI(title="FoodShare API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # development kosam mathrame
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(donations.router)
app.include_router(matching.router)
app.include_router(ngos.router)
app.include_router(verify.router)
app.include_router(admin.router)
app.include_router(pickups.router)
app.include_router(stats.router)


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/app/")


@app.get("/health")
def health():
    return {"status": "ok", "service": "FoodShare API"}


# Frontend: http://127.0.0.1:8000/app/
app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")