from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PATH_TO_SAVE = f"{Path(__file__).resolve().parent.parent}/static/cards/"

suits = ["♠", "♥", "♦", "♣"]
ranks = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]

card_width = 90
card_height = 135
corner_radius = 15
border_color = "black"
border_width = 1

color_map = {"♠": "black", "♣": "black", "♥": "red", "♦": "red"}

font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

settings_tech_cards = {
    8: "CONTINUE",
    13.5: "BRIDGE!"
}

try:
    font_little = ImageFont.truetype(font_path, 15)
    font_small = ImageFont.truetype(font_path, 24)
    font_large = ImageFont.truetype(font_path, 70)
    font_huge = ImageFont.truetype(font_path, 110)
except IOError:
    font_little = ImageFont.load_default()
    font_small = ImageFont.load_default()
    font_large = ImageFont.load_default()
    font_huge = ImageFont.load_default()


def create_rounded_rectangle(size, radius, fill):
    width, height = size
    rectangle = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(rectangle)
    draw.rounded_rectangle([0, 0, width-1, height], radius, fill=fill)
    return rectangle


def create_card_template(fill: tuple | str):
    card_img = Image.new("RGBA", (card_width, card_height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(card_img)

    draw.rounded_rectangle([0, 0, card_width-1, card_height], corner_radius + border_width, fill=border_color)
    card_background = create_rounded_rectangle(
        (card_width - border_width * 2, card_height - border_width * 2), corner_radius, fill=fill
    )
    card_img.paste(card_background, (border_width, border_width), card_background)

    return card_img


def create_closed_card():
    card_img = create_card_template(fill=(251, 186, 0))
    draw = ImageDraw.Draw(card_img)

    draw.text((4 + border_width, card_height / 3.5 + border_width), "Mebelka's", font=font_little, fill="black")
    draw.text((0.3 + border_width, card_height / 2.5 + border_width), "BRIDGE", font=font_small, fill="black")

    card_img = card_img.convert("P", palette=Image.ADAPTIVE)
    card_img.save(f"{PATH_TO_SAVE}closed_card.png", quality=1, optimize=True)


def create_playing_card(rank, suit):
    card_img = create_card_template(fill="white")
    draw = ImageDraw.Draw(card_img)

    color = color_map[suit]

    rank_bbox = draw.textbbox((0, 0), rank, font=font_small)
    rank_width = rank_bbox[2] - rank_bbox[0]
    draw.text((4, 4), rank, font=font_small, fill=color)

    suit_bbox = draw.textbbox((0, 0), suit, font=font_small)
    suit_width = suit_bbox[2] - suit_bbox[0]
    draw.text((4 + (rank_width - suit_width) / 2, 25), suit, font=font_small, fill=color)

    draw.text((card_width // 2 - 21, card_height // 2 - 39), suit, font=font_large, fill=color)

    draw.text((card_width - rank_width - 4, card_height - 31), rank, font=font_small, fill=color)

    suit_x = card_width - suit_width - 4
    draw.text((suit_x - (rank_width - suit_width) / 2, card_height - 52), suit, font=font_small, fill=color)

    return card_img


def create_suit_cards(suit):
    card_img = create_card_template(fill="white")
    draw = ImageDraw.Draw(card_img)

    draw.text((card_width // 2 - 33, card_height // 2 - 62), suit, font=font_huge, fill=color_map[suit])

    return card_img


def create_tech_cards(x, text):
    card_img = create_card_template(fill=(251, 186, 0))
    draw = ImageDraw.Draw(card_img)

    draw.text((x + border_width, card_height / 2.33 + border_width), text, font=font_little, fill="black")

    return card_img


def create_deck():
    create_closed_card()

    for suit in suits:
        card_img = create_suit_cards(suit)
        card_img = card_img.convert("P", palette=Image.ADAPTIVE)
        card_img.save(f"{PATH_TO_SAVE}{suit}.png", quality=1, optimize=True)

        for rank in ranks:
            card_img = create_playing_card(rank, suit)
            card_img = card_img.convert("P", palette=Image.ADAPTIVE)
            card_img.save(f"{PATH_TO_SAVE}{rank}_{suit}.png", quality=1, optimize=True)

    for x, text in settings_tech_cards.items():
        card_img = create_tech_cards(x, text)
        text = text[:-1] if x == 13.5 else text
        card_img = card_img.convert("P", palette=Image.ADAPTIVE)
        card_img.save(f"{PATH_TO_SAVE}{text.lower()}.png", quality=1, optimize=True)


create_deck()
