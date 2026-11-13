# FreshCheck: Deep Learning-Based Food Freshness Detection for Smart Food Donation

FreshCheck is the AI layer of **FoodShare**, a food donation platform that connects donors with NGOs and volunteers. A donor uploads a photo of the food, a deep learning model checks whether it is fresh or rotten, and only safe food is matched to a nearby NGO and picked up by a volunteer.

**Live demo:** https://freshcheck-wmj7.onrender.com/app/

> The demo runs on a free hosting plan. If nobody has opened it for a while, the first load can take up to a minute while the server wakes up.

B.Tech final-year project, Department of Artificial Intelligence and Data Science, Ramachandra College of Engineering (AY 2026-27).

## How it works

1. A donor posts surplus food with a photo, quantity, pickup address and expiry time.
2. The photo goes through the freshness model.
   - Rotten: rejected.
   - Fresh with confidence of at least 0.90: auto approved.
   - Fresh with lower confidence: sent to an admin for manual review.
3. Approved food is matched to the best NGO using distance (40%), urgency (30%) and NGO capacity (30%).
4. A volunteer accepts the pickup and marks it delivered.
5. Expired donations are closed automatically.

## Results

| Model | Accuracy |
|---|---|
| Baseline CNN | 98.18% |
| MobileNetV2 (transfer learning) | 99.56% (six classes), 99.70% (fresh vs rotten) |

- Rotten recall: 99.54%.
- Unsafe errors (rotten predicted as fresh) fell from 7 to 1 after adding the 0.90 confidence threshold with manual review.
- Dataset: fruits (apples, bananas, oranges), fresh and rotten, six classes, 10,901 training and 2,698 test images.
- Grad-CAM is used to show which part of the image the model looked at.

## Features

- Landing page with live statistics from the database
- Sign up, sign in and forgot password (6-digit reset code, hashed and valid for 15 minutes)
- Four roles: donor, NGO, volunteer, admin
- AI freshness check with confidence score and top-3 predictions
- NGO matching and volunteer pickup flow
- Admin overview with impact numbers (meals, food saved, CO2e avoided) and manual review queue
- Address search with OpenStreetMap (no API key needed)
- Live updates every 10 seconds

## Tech stack

| Layer | Technology |
|---|---|
| Model | TensorFlow / Keras, MobileNetV2, exported to TensorFlow Lite for serving |
| Backend | FastAPI, SQLAlchemy, JWT, bcrypt |
| Database | PostgreSQL (Neon), SQLite for quick local tests |
| Frontend | HTML, CSS, JavaScript (single page app served by FastAPI) |
| Hosting | Render |

## Project structure

```
backend/    FastAPI app (routes, services, models) and requirements
frontend/   Single page web app
ml/         Training notebook and trained models (.keras and .tflite)
docs/       Research document and presentation (PDF)
Dockerfile  Container build
```

## Run locally

Requires Python 3.11.

```
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install "psycopg[binary]"
uvicorn app.main:app --reload
```

Open http://localhost:8000/app/

Create `backend/.env` (this file is git-ignored) with:

```
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
SECRET_KEY=a-long-random-string
```

If `DATABASE_URL` is not set, the app falls back to a local SQLite file.

### Environment variables

| Name | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Database connection | local SQLite |
| `SECRET_KEY` | Signs login tokens | dev-only value, always change in production |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Creates the first admin account | none |
| `CONFIDENCE_THRESHOLD` | Auto-approve threshold | 0.90 |
| `SHOW_RESET_CODE` | Shows the reset code on screen (demo mode) | 1 |
| `FRESHCHECK_MODEL` | Path to the model file | `ml/mobilenet_finetuned.tflite` |

## Deployment

The live demo runs on Render with a TensorFlow-free build.

- Build command: `pip install -r backend/requirements-deploy.txt`
- Start command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment: `PYTHON_VERSION=3.11.9`, `DATABASE_URL`, `SECRET_KEY`

To regenerate the lightweight model from the Keras file, run `python ml/convert_to_tflite.py` inside the backend virtual environment.

## Limitations and future work

- The model recognises only apples, bananas and oranges. Other foods need more data.
- Cooked food cannot be judged from a photo alone, so it goes to manual review.
- The password reset code is shown on screen for demo purposes. A real email service should replace this.
- More food classes, a mobile app and real-time notifications are planned.

## Author

Jahnavi Madhyahanapu, Roll No. 23ME1A5440
Guide: Mr. Ramaswamy, Training and Placement Cell
