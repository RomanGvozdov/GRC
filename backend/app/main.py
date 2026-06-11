from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    audit,
    audits,
    auth,
    categories,
    comments,
    controls,
    dashboard,
    exports,
    frameworks,
    policies,
    reports,
    risks,
    users,
)
from app.database import Base, SessionLocal, engine
from app.seed import run_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        run_seed(db)
    yield


app = FastAPI(title="GRC", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # dev-сервер Vite; у проді той самий origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


api_routers = [
    auth.router,
    users.router,
    categories.router,
    risks.router,
    controls.router,
    frameworks.router,
    audits.router,
    policies.router,
    reports.router,
    dashboard.router,
    exports.router,
    audit.router,
    comments.router,
]
for router in api_routers:
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
