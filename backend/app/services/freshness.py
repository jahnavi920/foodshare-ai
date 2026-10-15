import io
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

CLASS_NAMES = ["freshapples", "freshbanana", "freshoranges",
               "rottenapples", "rottenbanana", "rottenoranges"]

DEFAULT_MODEL = Path(__file__).resolve().parents[3] / "ml" / "mobilenet_finetuned.keras"
MODEL_PATH = Path(os.getenv("FRESHCHECK_MODEL", str(DEFAULT_MODEL)))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.90"))


@lru_cache(maxsize=1)
def get_model():
    from tensorflow import keras  # ikkada import: server startup vegam ga undadaniki
    return keras.models.load_model(MODEL_PATH)


def decide(label: str, confidence: float) -> str:
    if label == "rotten":
        return "rejected"
    if confidence >= CONFIDENCE_THRESHOLD:
        return "auto_approved"
    return "manual_review"


def predict_image(image_bytes: bytes) -> dict:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise ValueError("File is not a valid image")

    img = img.resize((224, 224), Image.Resampling.BILINEAR)
    batch = np.asarray(img, dtype="float32")[None, ...]  # 0-255, preprocessing model lopala undi

    probs = get_model().predict(batch, verbose=0)[0]
    k = int(np.argmax(probs))
    confidence = float(probs[k])
    label = "fresh" if CLASS_NAMES[k].startswith("fresh") else "rotten"
    top3 = sorted(zip(CLASS_NAMES, probs), key=lambda x: x[1], reverse=True)[:3]

    return {
        "label": label,
        "predicted_class": CLASS_NAMES[k],
        "confidence": round(confidence, 4),
        "decision": decide(label, confidence),
        "threshold": CONFIDENCE_THRESHOLD,
        "top3": [{"class": n, "probability": round(float(p), 4)} for n, p in top3],
    }