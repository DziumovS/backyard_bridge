from itertools import product
from random import shuffle
from typing import List


class Card:

    def __init__(self, rank: str, suit: str):
        self.rank = rank
        self.suit = suit

    def __str__(self):
        return f"{self.rank} {self.suit}"

    # def can_play_on(self, other_card):
    #     return self.color == other_card.color or self.value == other_card.value or self.color == "wild"


class Deck:
    suits = ["♠", "♥", "♦", "♣"]
    ranks = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]

    def __init__(self):
        self.deck = self.create_deck()
        self.bounce_deck = []
        self.scores_rate = 1

    def __len__(self):
        return len(self.deck)

    def __str__(self):
        return f"Deck has {len(self.deck)} cards left"

    def create_deck(self) -> List[Card]:
        deck = [Card(rank, suit) for suit, rank in product(self.suits, self.ranks)]
        shuffle(deck)
        return deck

    def draw_card(self) -> Card:
        if not len(self.deck):
            self.flip()
        return self.deck.pop()

    def insert_to_bounce_deck(self, played_card: Card):
        self.bounce_deck.insert(0, played_card)

    def flip(self):
        self.deck = self.bounce_deck
        shuffle(self.deck)
        self.bounce_deck = []
        self.scores_rate += 1
        print("Scores: x2")
