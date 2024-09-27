from PIL import Image, ImageDraw, ImageFont

suits = ["♠", "♥", "♦", "♣"]
ranks = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]

card_width = 120
card_height = 180
corner_radius = 20
border_color = "black"
border_width = 1

color_map = {"♠": "black", "♣": "black", "♥": "red", "♦": "red"}


font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

path_to_save = "../static/cards/"

try:
    font_little = ImageFont.truetype(font_path, 20)
    font_small = ImageFont.truetype(font_path, 28)
    font_large = ImageFont.truetype(font_path, 80)
except IOError:
    font_little = ImageFont.load_default()
    font_small = ImageFont.load_default()
    font_large = ImageFont.load_default()


def create_rounded_rectangle(size, radius, fill):
    width, height = size
    rectangle = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(rectangle)
    draw.rounded_rectangle([0, 0, width, height], radius, fill=fill)
    return rectangle


def create_card(rank, suit):
    card_img = Image.new("RGBA", (card_width, card_height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(card_img)

    draw.rounded_rectangle(
        [-1, 0, card_width, card_height],
        corner_radius + border_width,
        fill=border_color
    )

    card_background = create_rounded_rectangle((card_width - border_width * 2, card_height - border_width * 2), corner_radius, "white")
    card_img.paste(card_background, (border_width, border_width), card_background)

    color = color_map[suit]

    rank_bbox = draw.textbbox((0, 0), rank, font=font_small)
    rank_width = rank_bbox[2] - rank_bbox[0]
    draw.text((5, 5), rank, font=font_small, fill=color)

    suit_bbox = draw.textbbox((0, 0), suit, font=font_small)
    suit_width = suit_bbox[2] - suit_bbox[0]
    draw.text((5 + (rank_width - suit_width) / 2, 35), suit, font=font_small, fill=color)

    draw.text((card_width // 2 - 25, card_height // 2 - 40), suit, font=font_large, fill=color)

    draw.text((card_width - rank_width - 5, card_height - 40), rank, font=font_small, fill=color)

    suit_x = card_width - suit_width - 5
    draw.text((suit_x - (rank_width - suit_width) / 2, card_height - 70), suit, font=font_small, fill=color)

    return card_img


for suit in suits:
    for rank in ranks:
        card_img = create_card(rank, suit)
        file_name = f"{rank}_{suit}.png"
        card_img.save(f"{path_to_save}{file_name}")


closed_card_img = Image.new("RGBA", (card_width, card_height), (255, 255, 255, 0))
draw = ImageDraw.Draw(closed_card_img)
draw.rounded_rectangle(
    [-1, 0, card_width, card_height],
    corner_radius + border_width,
    fill=border_color
)

closed_card_background = create_rounded_rectangle(
    (card_width - border_width * 2, card_height - border_width * 2),
    corner_radius,
    fill=(251, 186, 0)
)
closed_card_img.paste(closed_card_background, (border_width, border_width), closed_card_background)

draw.text((5 + border_width, card_height / 3 + border_width), "Mebelka's", font=font_little, fill="black")
draw.text((7 + border_width, card_height / 2 + border_width), "BRIDGE", font=font_small, fill="black")

closed_card_img.save(f"{path_to_save}closed_card.png")
