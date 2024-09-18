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
        return [{"rank": card.rank, "suit": card.suit} for card in self.hand]

    def draw_card(self, deck: Deck):
        self.hand.append(deck.draw_card())

    def play_card(self, card: Card, current_card: Card) -> bool:
        if card.can_play_on(current_card):
            self.hand.remove(card)
            return True
        return False

    def has_won(self) -> bool:
        return len(self.hand) == 0
