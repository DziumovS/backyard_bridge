from typing import Dict, List
from dataclasses import dataclass

from fastapi import WebSocket

from src.deck.models import Deck, Card


class User:
    def __init__(self, user_id: str, websocket: WebSocket, user_name: str):
        self.user_id: str = user_id
        self.websocket: WebSocket = websocket
        self.user_name: str = user_name


@dataclass
class PlayerOptions:
    must_draw: int = 0
    must_skip: bool = False
    can_draw: bool = True
    can_skip: bool = False


class Player(User):
    def __init__(self, user_id: str, websocket: WebSocket, user_name: str):
        super().__init__(user_id, websocket, user_name)
        self.hand: List = []
        self.scores: int = 0
        self.options: PlayerOptions = PlayerOptions()

    def set_default_options(self, can_draw: bool = True):
        self.options = PlayerOptions()
        self.options.can_draw = can_draw

    def options_to_dict(self) -> Dict:
        return {
            "must_draw": self.options.must_draw,
            "must_skip": self.options.must_skip,
            "can_draw": self.options.can_draw,
            "can_skip": self.options.can_skip
        }

    def hand_to_dict(self) -> List:
        return [card.card_to_dict() for card in self.hand]

    def dict_to_card(self, card: Dict) -> Card:
        for card_in_hand in self.hand:
            if card_in_hand.rank == card["rank"] and card_in_hand.suit == card["suit"]:
                return card_in_hand

    def draw_card(self, deck: Deck):
        self.hand.append(deck.draw_card())

    def get_playable_cards(self, current_card: Card, chosen_suit: dict | None = None, to_dict: bool = False,
                           j: bool = False) -> List[Dict | Card]:
        return [
            card.card_to_dict() if to_dict else card
            for card in self.hand
            if card.can_play_on(current_card=current_card, chosen_suit=chosen_suit, j=j)
        ]

    def prepare_playable_cards(self, game, chosen_suit: dict | None = None, playable_cards: bool = True):
        if self.options.must_draw or self.options.must_skip or not playable_cards:
            return ()
        else:
            if game.current_card.rank == "J" and game.chosen_suit and game.chosen_suit["chooser_id"] == self.user_id:
                return self.get_playable_cards(current_card=game.current_card, to_dict=True, j=True)
            else:
                return self.get_playable_cards(
                    current_card=game.current_card,
                    chosen_suit=chosen_suit,
                    to_dict=True
                )

    def has_won(self, card: Card) -> bool:
        return len(self.hand) == 0 and card.rank != "6"

    def reset_hand(self):
        self.hand = []

    def reset_score(self):
        self.scores = 0
