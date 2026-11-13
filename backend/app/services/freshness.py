import io
import os
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

CLASS_NAMES = ["freshapples", "freshbanana", "freshoranges",
               "rottenapples", "rottenbanana", "rottenoranges"]

ML_DIR = Path(__file__).resolve().parents[3] / "ml"
MODEL_PATH = Path(os.getenv("FRESHCHECK_MODEL", str(ML_DIR / "mobilenet_finetuned.tflite")))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.90"))

_lock = threading.Lock()  # a TFLite interpreter is not thread-safe


def _make_interpreter():
    try:  # light runtime used in deployment
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:  # local development with full TensorFlow
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter
    return Interpreter(model_path=str(MODEL_PATH))


@lru_cache(maxsize=1)
def get_model():
    interp = _make_interpreter()
    interp.allocate_tensors()
    return interp


def _run(batch: np.ndarray) -> np.ndarray:
    interp = get_model()
    inp = interp.get_input_details()[0]
    out = interp.get_output_details()[0]
    with _lock:
        interp.set_tensor(inp["index"], batch)
        interp.invoke()
        return interp.get_tensor(out["index"])[0].copy()


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
    batch = np.asarray(img, dtype="float32")[None, ...]  # 0-255, preprocessing is inside the model

    probs = _run(batch)
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
