from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models  # noqa: F401  (tables register avvadaniki)
from .routes import admin, auth, donations, matching, ngos, verify

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FoodShare API", version="0.1.0")

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


@app.get("/health")
def health():
    return {"status": "ok", "service": "FoodShare API"}