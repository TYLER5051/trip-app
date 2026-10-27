from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from rate_limit import limiter
from routers.participants import router as part_router
from routers.items import router as items_router
from routers.authentication import router as auth_router
from routers.trips import router as trips_router
import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Trip API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(part_router)
app.include_router(items_router)
app.include_router(auth_router)
app.include_router(trips_router)

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")

