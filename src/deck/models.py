from itertools import product
from random import shuffle, choice


class Card:
    def __init__(self, rank: str, suit: str):
        self.rank = rank
        self.suit = suit

    def __str__(self):
        return f"{self.rank} {self.suit}"

    def can_play_on(self, current_card, chosen_suit: dict | None = None, j: bool = False) -> bool:
        if chosen_suit:
            return self.suit == chosen_suit["suit"] or self.rank == "J"
        if j:
            return self.rank == "J"
        return self.rank == current_card.rank or self.suit == current_card.suit or self.rank == "J"

    def card_to_dict(self) -> dict:
        return {"rank": self.rank, "suit": self.suit}


class Deck:
    suits = ["♠", "♥", "♦", "♣"]
    ranks = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    special_cards = ["6", "7", "8", "J", "A"]
    color_map = {"♠": "black", "♣": "black", "♥": "red", "♦": "red"}

    def __init__(self):
        self.deck = self.create_deck()
        self.bounce_deck = []
        self.scores_rate = 1

    def __len__(self):
        return len(self.deck)

    def __str__(self):
        return f"Deck has {len(self.deck)} cards left"

    def __del__(self):
        print("Deck has been deleted.")

    def create_deck(self) -> list[Card]:
        deck = [Card(rank, suit) for suit, rank in product(self.suits, self.ranks)]
        shuffle(deck)
        return deck

    def add_to_deck_random_card(self) -> None:
        self.deck.append(Card(rank=choice(self.ranks), suit=choice(self.suits)))

    def is_decks_empty(self) -> bool:
        return not self.deck and not self.bounce_deck

    def is_decks_empty_for_eight(self, card: Card) -> bool:
        return card.rank == "8" and not self.deck and len(self.bounce_deck) == 1

    def draw_card(self) -> Card:
        if not len(self.deck):
            self.flip()
        return self.deck.pop()

    def insert_to_bounce_deck(self, previous_card: Card) -> None:
        if previous_card:
            self.bounce_deck.insert(0, previous_card)

    def flip(self) -> None:
        self.deck = self.bounce_deck
        shuffle(self.deck)
        self.bounce_deck = []
        self.scores_rate += 1
