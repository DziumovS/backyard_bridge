from random import shuffle
from itertools import product


class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def __str__(self):
        return f"{self.rank} of {self.suit}"


class Deck:
    def __init__(self):
        self.suits = ("spades", "hearts", "diamonds", "clubs")
        self.values = ("six", "seven", "eight", "nine", "ten", "jack", "queen", "king", "ace")
        self.main_deck = []
        self.bounce_deck = []
        self.build()

    def build(self):
        self.main_deck = [Card(rank, suit) for suit, rank in product(self.suits, self.values)]
        shuffle(self.main_deck)

    def pop(self):
        if not len(self.main_deck):
            self.flip()
        last_card_from_main_deck = self.main_deck.pop()
        self.bounce_deck.insert(0, last_card_from_main_deck)

    def flip(self):
        self.main_deck = self.bounce_deck
        self.bounce_deck = []
        print("Scores: x2")

    def __len__(self):
        return len(self.main_deck)

    def __str__(self):
        return f"Deck has {len(self.main_deck)} cards left"


class Player:
    def __init__(self, name, is_host, id):
        self.name = name
        self.is_host = is_host
        self.id = id
        self.hand = []

    def __len__(self):
        return len(self.hand)

    def __str__(self):
        return str(self.name) + "\n" + "".join([str(c) + "\n" for c in self.hand])[:-1]

    def draw_card(self, card):
        self.hand.append(card)

    def sort_hand(self):
        non_uber_cards = [c for c in self.hand if c.uber is not c.suit]
        non_uber_cards.sort(key=lambda c: c.rank)

        uber_cards = [c for c in self.hand if c.uber is c.suit]
        uber_cards.sort(key=lambda c: c.rank)

        self.hand = non_uber_cards + uber_cards
