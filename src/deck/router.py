from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse


router = APIRouter(
    prefix="",
    tags=["Deck"]
)


cards_directory = Path(__file__).parent.parent.absolute() / "static/cards"
card_urls = tuple(
    f"/static/cards/{card.name}"
    for card in sorted(cards_directory.iterdir())
    if card.is_file()
)


@router.get("/get_cards")
async def get_card_images():
    return JSONResponse(content=card_urls)
