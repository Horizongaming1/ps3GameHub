from fastapi import APIRouter

from app.api.routes.games import router as games_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.scan import router as scan_router
from app.api.routes.targets import router as targets_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(games_router)
api_router.include_router(scan_router)
api_router.include_router(targets_router)
api_router.include_router(jobs_router)
