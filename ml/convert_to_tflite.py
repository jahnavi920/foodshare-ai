"""Convert ml/mobilenet_finetuned.keras to ml/mobilenet_finetuned.tflite and verify it."""
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow import keras

ML = Path(__file__).resolve().parent
src = ML / "mobilenet_finetuned.keras"
dst = ML / "mobilenet_finetuned.tflite"

model = keras.models.load_model(src)
converter = tf.lite.TFLiteConverter.from_keras_model(model)
dst.write_bytes(converter.convert())
print("saved", dst, round(dst.stat().st_size / 1e6, 2), "MB")

# verify: same predictions as the keras model
interp = tf.lite.Interpreter(model_path=str(dst))
interp.allocate_tensors()
inp = interp.get_input_details()[0]
out = interp.get_output_details()[0]
print("input shape", inp["shape"], "output shape", out["shape"])

rng = np.random.default_rng(0)
worst = 0.0
same = 0
for _ in range(10):
    x = rng.uniform(0, 255, size=(1, 224, 224, 3)).astype("float32")
    a = model.predict(x, verbose=0)[0]
    interp.set_tensor(inp["index"], x)
    interp.invoke()
    b = interp.get_tensor(out["index"])[0]
    worst = max(worst, float(np.abs(a - b).max()))
    same += int(np.argmax(a) == np.argmax(b))
print("max abs difference:", worst, "| same top class:", same, "/ 10")
