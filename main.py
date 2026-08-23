from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.lobby.router import router as lobby_router
from src.game.router import router as game_router
from src.deck.router import router as deck_router

app = FastAPI(
    title="Backyard bridge"
)

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent.absolute() / "src/static"),
    name="static",
)

app.include_router(lobby_router)
app.include_router(game_router)
app.include_router(deck_router)

templates = Jinja2Templates(directory="src/templates")

origins = [
    "http://localhost:8000",
    ""
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Content-Type", "Set-Cookie", "Access-Control-Allow-Headers", "Access-Control-Allow-Origin",
                   "Authorization"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"
    elif request.url.path == "/get_cards":
        response.headers["Cache-Control"] = "public, max-age=86400"
    else:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse(request, "index.html")
