import random
from typing import List, Optional, Dict
from dataclasses import dataclass

from fastapi import WebSocket

from src.connection.manager import ConnectionManager
from src.user.models import Player
from src.deck.models import Card, Deck


@dataclass
class FourOfAKindTracker:
    current_rank: str = None
    count: int = 0

    def checking(self, card_rank: str) -> bool:
        if card_rank != self.current_rank:
            self.current_rank = card_rank
            self.count = 1
        else:
            self.count += 1

        return self.count == 4


class Game:
    def __init__(self, game_id: str, players: List[Player]):
        self.deck = Deck()
        self.game_id = game_id
        self.players = self.shuffle_players(players=players)
        self.is_active = True
        self.current_player_index = 0
        self.chosen_suit = None
        self.four_of_a_kind_tracker: FourOfAKindTracker = FourOfAKindTracker()
        self.last_cards_j = {}

        for player in self.players:
            for _ in range(5):
                player.draw_card(self.deck)

        self.current_card = self.card_distribution()

    def __del__(self):
        print(f"Game '{self.game_id}' has been deleted.")

    def calculate_scores(self):
        points_mapping = {
            "10": 10,
            "Q": 10,
            "K": 10,
            "A": 15
        }

        for player in self.players:
            points = 0
            only_jacks = all(card.rank == "J" for card in player.hand)

            points_mapping["J"] = 20 if only_jacks else 10

            for card in player.hand:
                if card.rank in points_mapping:
                    points += points_mapping[card.rank]

            player.scores += (points * self.deck.scores_rate)
            if player.user_id in self.last_cards_j and only_jacks:
                player.scores -= ((self.last_cards_j[player.user_id] * points_mapping["J"]) * self.deck.scores_rate)
            player.scores = 0 if player.scores == 125 else player.scores

    def get_players_game_results(self):
        players_scores = []
        losers = []
        winners = []
        for player in self.players:
            player_info = {"player": player.user_name, "scores": player.scores}
            players_scores.append(player_info)
            losers.append(player_info) if player.scores > 125 else winners.append(player_info)
        return players_scores, losers, winners

    def is_it_bridge(self, card: Card) -> bool:
        return self.four_of_a_kind_tracker.checking(card.rank)

    def card_distribution(self) -> Card:
        random.shuffle(self.get_current_player().hand)
        self.current_card = self.get_current_player().hand[0]
        return self.current_card

    def current_card_to_dict(self) -> Dict:
        return self.current_card.card_to_dict()

    def shuffle_players(self, players: List[Player]) -> List[Player]:
        random.shuffle(players)
        return players

    def get_player_or_none(self, user_id: str) -> Optional[Player]:
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    def remove_player(self, user_id: str):
        self.players = [player for player in self.players if player.user_id != user_id]

    def get_players(self) -> List[Dict]:
        return [
            {
                "user_id": player.user_id,
                "user_name": player.user_name
            } for player in self.players
        ]

    def is_current_player(self, player_id: str) -> bool:
        current_player = self.players[self.current_player_index]
        return current_player.user_id == player_id

    def get_current_player(self) -> Player:
        return self.players[self.current_player_index]

    def get_next_player(self) -> Player:
        return self.players[(self.current_player_index + 1) % len(self.players)]

    def get_players_websocket(self) -> List[WebSocket]:
        return [player.websocket for player in self.players]

    def next_player(self):
        self.current_player_index = (self.current_player_index + 1) % len(self.players)

    def end_game(self):
        self.is_active = False
        print(f"Game {self.game_id} has ended.")

    def remove_played_card(self, current_player: Player, card: Card | None):
        current_player.hand.remove(self.current_card)
        self.deck.insert_to_bounce_deck(previous_card=card)

    def handle_card_six(self, current_player: Player):
        playable_cards = current_player.get_playable_cards(
            current_card=self.current_card,
            chosen_suit=self.chosen_suit,
        )
        if playable_cards:
            current_player.options.can_skip = False
            current_player.options.can_draw = True
        else:
            current_player.options.must_draw += 1

    def _handle_card_six(self, current_player: Player, card: Card):
        self.remove_played_card(current_player=current_player, card=card)

        self.handle_card_six(current_player=current_player)

    def _handle_card_seven(self, current_player: Player, card: Card):
        self.remove_played_card(current_player=current_player, card=card)
        current_player.options.must_skip = True

        next_player = self.get_next_player()
        next_player.set_default_options()
        next_player.options.must_draw += 1

    def _handle_card_eight(self, current_player: Player, card: Card):
        self.remove_played_card(current_player=current_player, card=card)
        current_player.options.must_skip = True

        next_player = self.get_next_player()
        next_player.set_default_options()
        next_player.options.must_draw += 2
        next_player.options.must_skip = True

    def _handle_card_jack(self, current_player: Player, card: Card):
        self.remove_played_card(current_player=current_player, card=card)
        current_player.options.can_draw = False
        current_player.options.can_skip = True

        if current_player.user_id not in self.last_cards_j:
            self.last_cards_j[current_player.user_id] = 1
        else:
            self.last_cards_j[current_player.user_id] += 1

        if not current_player.get_playable_cards(current_card=self.current_card, j=True):
            current_player.options.must_skip = True

        next_player = self.get_next_player()
        next_player.set_default_options()

    def _handle_card_ace(self, current_player: Player, card: Card):
        self.remove_played_card(current_player=current_player, card=card)
        current_player.options.must_skip = True

        next_player = self.get_next_player()
        next_player.set_default_options()
        next_player.options.must_skip = True

    def _handle_normal_card(self, current_player: Player, card: Card):
        self.remove_played_card(current_player=current_player, card=card)
        current_player.set_default_options()
        current_player.options.must_skip = True

    def handle_special_cards(self, current_player: Player, card: Card):
        match self.current_card.rank:
            case "6":
                self._handle_card_six(current_player=current_player, card=card)
            case "7":
                self._handle_card_seven(current_player=current_player, card=card)
            case "8":
                self._handle_card_eight(current_player=current_player, card=card)
            case "J":
                self._handle_card_jack(current_player=current_player, card=card)
            case "A":
                self._handle_card_ace(current_player=current_player, card=card)
            case _:
                self._handle_normal_card(current_player=current_player, card=card)
