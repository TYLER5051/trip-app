# Smart Trip App

Full-stack travel planner: **FastAPI** backend (PostgreSQL) + **Vue 3 / Vite** frontend.

| Component | Tech | Port |
|---|---|---|
| Frontend | Vue 3 + Vite | `http://localhost:5173` |
| Backend API | FastAPI + Uvicorn | `http://localhost:8000` (`/docs`) |
| Database | PostgreSQL 15 (Docker) | `localhost:5432` |
| DB Admin | pgAdmin 4 (Docker) | `http://localhost:5050` |

## Structure

```
trip_app/
├── trip_backend/          # FastAPI + SQLAlchemy
│   ├── main.py            # routes + CORS
│   ├── database.py        # engine / session
│   ├── models.py          # SQLAlchemy models
│   ├── schemas.py         # Pydantic schemas
│   ├── auth.py            # JWT + bcrypt
│   ├── docker-compose.yaml# db + pgadmin
│   └── .env.example       # copy to .env
└── trip_frontend/         # Vue 3 + Vite
    ├── src/services/api.js
    └── .env.example       # copy to .env
```

## Local setup

### 1. Backend

```bash
cd trip_backend
cp .env.example .env
# edit .env: set your own DB credentials + a strong SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(64))"

docker compose up -d db          # PostgreSQL on :5432
docker compose up -d pgadmin     # optional, on :5050

python -m venv venv
source venv/Scripts/activate     # Windows: venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Tables are created automatically on first startup (`Base.metadata.create_all`).

### 2. Frontend

```bash
cd trip_frontend
cp .env.example .env             # VITE_API_URL=http://localhost:8000
npm install
npm run dev                      # http://localhost:5173
```

> The frontend port is the Vite default (`5173`). The backend CORS policy allows
> `http://localhost:5173` and `http://localhost:3000` — adjust
> `allow_origins` in `trip_backend/main.py` if you change the port.

## API

Interactive docs: <http://localhost:8000/docs>

`POST /register` · `POST /login` · `GET/POST /trips/` · `GET/DELETE /trips/{id}` ·
categories · items · participants. All endpoints except `/register` and `/login`
require `Authorization: Bearer <token>`.

## Security notes

- `.env` files are **git-ignored**; only `.env.example` templates are committed.
- Never commit real credentials — rotate `SECRET_KEY` if it is ever exposed.
- `SECRET_KEY` must be set, otherwise JWT signing fails at import time.
- `ACCESS_TOKEN_EXPIRE_MINUTES` is required by `auth.py` (see `.env.example`).
