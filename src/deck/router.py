from pathlib import Path
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse


router = APIRouter(
    prefix="",
    tags=["Deck"]
)


path_to_cards = f"{Path(__file__).parent.parent.absolute()}/static/cards/"


@router.get("/get_cards")
async def get_card_images():
    card_files = [f for f in os.listdir(path_to_cards) if os.path.isfile(os.path.join(path_to_cards, f))]
    card_urls = [f"/static/cards/{file}" for file in card_files]
    return JSONResponse(content=card_urls)
