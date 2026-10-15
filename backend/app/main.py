import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from . import models  # noqa: F401  (tables register avvadaniki)
from .routes import admin, auth, donations, matching, ngos, pickups, stats, verify
from .services.expiry import expire_overdue

Base.metadata.create_all(bind=engine)


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


@app.get("/health")
def health():
    return {"status": "ok", "service": "FoodShare API"}