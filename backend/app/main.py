from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ai,
    audit,
    audits,
    baselines,
    imports,
    my_tasks,
    poam,
    profiles,
    ssp,
    systems,
    auth,
    categories,
    comments,
    controls,
    dashboard,
    exports,
    frameworks,
    policies,
    rbac,
    reports,
    risks,
    users,
)
from app.config import get_settings
from app.database import SessionLocal
from app.migrations import run_migrations
from app.seed import run_seed
from app.services.notify import send_daily_digest


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    with SessionLocal() as db:
        run_seed(db)
    scheduler = None
    if get_settings().scheduler_enabled:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler(timezone="Europe/Kyiv")
        scheduler.add_job(
            send_daily_digest, CronTrigger(hour=get_settings().digest_hour, minute=0)
        )
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


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
    systems.router,
    baselines.router,
    profiles.router,
    ssp.router,
    poam.router,
    audits.router,
    policies.router,
    my_tasks.router,
    imports.router,
    rbac.router,
    reports.router,
    dashboard.router,
    exports.router,
    audit.router,
    comments.router,
    ai.router,
]
for router in api_routers:
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
