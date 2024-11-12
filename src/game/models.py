import random
import asyncio
from typing import List, Optional, Dict
from dataclasses import dataclass

from fastapi import WebSocket

from src.user.models import Player
from src.deck.models import Card, Deck
from src.game.handlers import CardHandler


@dataclass
class FourOfAKindTracker:
    current_rank: str = None
    count: int = 0

    def checking(self, card_rank: str) -> bool:
        if card_rank == self.current_rank:
            self.count = 1 if self.count == 4 else self.count + 1
        else:
            self.current_rank = card_rank
            self.count = 1

        return self.count == 4 and self.current_rank != "6"

    def reset(self):
        self.current_rank = None
        self.count = 0


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
        self.why_end = None
        self.card_handler = CardHandler(game_instance=self)
        self.all_connected_event = asyncio.Event()

        for player in self.players:
            player.websocket = None
            for _ in range(5):
                player.draw_card(self.deck)

        self.current_card = self.card_distribution()

    def __del__(self):
        print(f"Game '{self.game_id}' has been deleted.")

    async def wait_until_all_ready(self):
        await self.all_connected_event.wait()

    def check_all_players_connected(self):
        if all(player.websocket for player in self.players):
            self.all_connected_event.set()

    def add_player_websocket(self, player_id: str, websocket: WebSocket):
        player = self.get_player_or_none(user_id=player_id)
        if player:
            player.websocket = websocket
            self.check_all_players_connected()

    def reset_game(self):
        self.deck = Deck()
        self.is_active = True
        self.current_player_index = 0
        self.chosen_suit = None
        self.four_of_a_kind_tracker.reset()
        self.last_cards_j = {}
        self.why_end = None

        self.shuffle_players(players=self.players)

        if any(player.scores > 125 for player in self.players):
            self.reset_players_scores()

        for player in self.players:
            player.reset_hand()
            player.set_default_options()
            for _ in range(5):
                player.draw_card(self.deck)

        self.current_card = self.card_distribution()

    def reset_players_scores(self):
        for player in self.players:
            player.reset_score()

    def calculate_scores(self):
        points_mapping = {
            "10": 10,
            "Q": 10,
            "K": 10,
            "A": 15
        }

        result = []

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

            result.append({"player_id": player.user_id, "scores": player.scores})

        return result

    def get_players_game_results(self):
        players_scores, losers, winners = [], [], []

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

    def get_player_or_none(self, user_id: str) -> Player | None:
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    def remove_player(self, player: Player):
        if player in self.players:
            self.players.remove(player)

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

    def remove_played_card(self, current_player: Player, card: Card | None):
        current_player.hand.remove(self.current_card)
        self.deck.insert_to_bounce_deck(previous_card=card)

    def get_game_over_message(self, current_player: Player):
        players_scores, losers, winners = self.get_players_game_results()
        player_username = current_player.user_name

        match self.why_end:
            case "bridge":
                message = f"<b>{player_username}</b> call 'bridge', so the match is over.<br><br>"
            case "empty_deck":
                message = f"<b>No more cards</b> in the deck, so the match is over.<br><br>"
            case _:
                message = f"<b>{player_username}</b> has won: he has no more cards, so the match is over.<br><br>"

        results = f"{message}Now the scores are:<br>"
        results += "<br>".join(
            [
                f"&nbsp;&nbsp;<b>{player['player']}</b>: <b>{player['scores']}</b> points"
                for player in players_scores
            ]
        )

        if losers:
            results = (f"{message}Also, the <b>game is over too</b> because we have "
                       f"{"a loser" if len(losers) == 1 else "losers"} by points:<br>")
            results += "<br>".join(
                [
                    f"&nbsp;&nbsp;<b>{user['player']}</b>: <b>{user['scores']}</b> points"
                    for user in losers
                ]
            )

            if winners:
                w_ws, g_gs = ("winner", "god") if len(winners) == 1 else ("winners", "gods")
                results += f"<br><br>And <b>congratulations</b> to the {w_ws} of this game:<br>"
                results += "<br>".join(
                    [
                        f"&nbsp;&nbsp;<b>{user['player']}</b>: <b>{user['scores']}</b> points"
                        for user in winners
                    ]
                )
                results += f"<br>You fought like {g_gs}!"

        return message, results
