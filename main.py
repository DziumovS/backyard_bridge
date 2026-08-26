from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from src.lobby.router import router as lobby_router
from src.game.router import router as game_router
from src.deck.router import router as deck_router
from src.config import BASE_DIR, get_allowed_origins, use_dev_assets

app = FastAPI(
    title="Backyard bridge"
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "src/static"),
    name="static",
)

app.include_router(lobby_router)
app.include_router(game_router)
app.include_router(deck_router)

templates = Jinja2Templates(directory=BASE_DIR / "src/templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Content-Type", "Set-Cookie", "Access-Control-Allow-Headers", "Access-Control-Allow-Origin",
                   "Authorization"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; connect-src 'self' ws: wss:; "
        "frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; "
        "script-src 'self'; style-src 'self' 'unsafe-inline'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.endswith((".js", ".css")):
        response.headers["Cache-Control"] = "no-cache"
    elif request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif request.url.path == "/get_cards":
        response.headers["Cache-Control"] = "public, max-age=86400"
    else:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    dev_assets = use_dev_assets()
    return templates.TemplateResponse(
        request,
        "index.dev.html" if dev_assets else "index.html",
        {"asset_suffix": ".dev" if dev_assets else ""},
    )


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def chrome_devtools_probe():
    return Response(status_code=204)
