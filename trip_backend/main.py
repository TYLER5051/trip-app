import logging
import os
import time
import uuid
import models
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from database import engine
from rate_limit import limiter
from routers.participants import router as part_router
from routers.items import router as items_router
from routers.authentication import router as auth_router
from routers.trips import router as trips_router

logger = logging.getLogger("trip_api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Trip API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_logging(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s %s -> %s (%.1fms)",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-Id"] = request_id
    return response


@app.get("/healthz")
def healthz():
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error"})
    return {"status": "ok"}


app.include_router(part_router)
app.include_router(items_router)
app.include_router(auth_router)
app.include_router(trips_router)


@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")
