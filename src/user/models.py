from typing import Dict

from fastapi import WebSocket

from src.deck.models import Deck, Card


class User:
    def __init__(self, user_id: str, websocket: WebSocket, user_name: str):
        self.user_id = user_id
        self.websocket = websocket
        self.user_name = user_name


class Player(User):
    def __init__(self, user_id: str, websocket: WebSocket, user_name: str):
        super().__init__(user_id, websocket, user_name)
        self.hand = []

    def hand_to_dict(self) -> list:
        return [card.card_to_dict() for card in self.hand]

    def dict_to_card(self, card: Dict) -> Card:
        for card_in_hand in self.hand:
            if card_in_hand.rank == card["rank"] and card_in_hand.suit == card["suit"]:
                return card_in_hand

    def draw_card(self, deck: Deck):
        self.hand.append(deck.draw_card())

    def play_card(self, card: Card, current_card: Card, chosen_suit: str | None = None) -> bool:
        if card.can_play_on(current_card=current_card, chosen_suit=chosen_suit):
            self.hand.remove(card)

    def get_playable_cards(self, current_card: Card, chosen_suit: str | None, to_dict: bool = False):
        return [
            card.card_to_dict() if to_dict else card
            for card in self.hand
            if card.can_play_on(current_card=current_card, chosen_suit=chosen_suit)
        ]

    def has_won(self) -> bool:
        return len(self.hand) == 0
