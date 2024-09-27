from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.lobby.router import router as lobby_router
from src.game.router import router as game_router

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

templates = Jinja2Templates(directory="src/templates")

origins = [
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Content-Type", "Set-Cookie", "Access-Control-Allow-Headers", "Access-Control-Allow-Origin",
                   "Authorization"],
)


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
