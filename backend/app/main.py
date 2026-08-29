from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, engine, run_migrations
from .routers import auth, groups, expenses, ws

Base.metadata.create_all(bind=engine)
run_migrations()

app = FastAPI(title="Сплит-копилка")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_for_static(request: Request, call_next):
    """Force the browser to always revalidate HTML/CSS/JS instead of
    relying on heuristic caching, which otherwise can silently serve a
    stale JS file after a frontend update (still fast: revalidation
    returns 304 when the file hasn't actually changed)."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response

app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(expenses.router)
app.include_router(expenses.balances_router)
app.include_router(expenses.analytics_router)
app.include_router(ws.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
