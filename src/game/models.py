import random
from typing import List, Optional, Dict

from fastapi import WebSocket

from src.connection.manager import ConnectionManager
from src.user.models import Player
from src.deck.models import Card, Deck


class Game:
    def __init__(self, game_id: str, players: List[Player]):
        self.deck = Deck()
        self.game_id = game_id
        self.players = self.shuffle_players(players=players)
        self.is_active = True
        self.first_move = True
        self.current_player_index = 0
        self.chosen_suit = None

        for player in self.players:
            for _ in range(5):
                player.draw_card(self.deck)

        self.current_card = self.card_distribution()

    def card_distribution(self) -> Card:
        current_player_hand = self.players[self.current_player_index].hand
        played_card = current_player_hand.pop()
        self.deck.insert_to_bounce_deck(played_card=played_card)
        return played_card

    def current_card_to_dict(self) -> Dict:
        return self.current_card.card_to_dict()

    def shuffle_players(self, players: List[Player]) -> List[Player]:
        random.shuffle(players)
        return players

    def remove_game(self, game_id: str):
        if game_id in self.games:
            del self.games[game_id]

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
                "player_id": player.user_id,
                "player_name": player.user_name,
                "player_hand": player.hand
            } for player in self.players]

    def get_players_websocket(self) -> List[WebSocket]:
        return [player.websocket for player in self.players]

    def next_player(self):
        self.current_player_index = (self.current_player_index + 1) % len(self.players)

    def end_game(self):
        self.is_active = False
        print(f"Game {self.game_id} has ended.")

    def play(self):
        while self.is_active:
            player = self.players[self.current_player_index]
            print(f"\n{player.user_name}'s turn. Current card: {self.current_card}")
            print(f"Hand: {', '.join(str(card) for card in player.hand)}")

            if self.first_move:
                self.first_turn(player=player)
            else:
                self.player_turn(player=player)

            if player.has_won():
                print(f"{player.user_name} has won the game!")
                self.end_game()
                break

            self.next_player()

    def player_turn(self, player: Player):
        playable_cards = player.get_playable_cards(current_card=self.current_card)
        if not playable_cards:
            print(f"{player.user_name} has no playable cards, drawing a card.")
            player.draw_card(self.deck)
            print(f"Hand: {', '.join(str(card) for card in player.hand)}")
            playable_cards = player.get_playable_cards(current_card=self.current_card)
            if not playable_cards:
                print(f"{player.user_name} still has no playable cards. Next player turn.")
                return

        print("Playable cards:")
        for i, card in enumerate(playable_cards):
            print(f"{i + 1}: {card}")

        choice = int(input("Choose a card to play (enter the number): ")) - 1  #######
        chosen_card = playable_cards[choice]  #######
        player.play_card(chosen_card, self.current_card)
        self.current_card = chosen_card
        self.deck.insert_to_bounce_deck(chosen_card)

        self.handle_special_cards(player=player)

    def first_turn(self, player: Player):
        print("It's first_turn function!")
        if self.first_move:
            self.first_move = False

            if self.current_card.rank in self.deck.special_cards:
                self.handle_special_cards(player=player)
                return

            # playable_cards = [card for card in player.hand if card.can_play_on(other_card=self.current_card)]
            # if not playable_cards:
            #     print(f"{player.user_name} has no playable cards.")
            #     return
            #
            # else:
            #     print("Playable cards:")
            #     for i, card in enumerate(playable_cards):
            #         print(f"{i + 1}: {card}")
            #
            #     choice = int(input("Choose a card to play (enter the number): ")) - 1  #######
            #     chosen_card = playable_cards[choice]  #######
            #     player.play_card(chosen_card, self.current_card)
            #     self.current_card = chosen_card
            #     self.deck.insert_to_bounce_deck(chosen_card)
            #     return

    def _handle_card_six(self, player: Player):
        while True:
            print(f"Current card: {self.current_card}")
            playable_cards = player.get_playable_cards(current_card=self.current_card)
            if not playable_cards:
                player.draw_card(self.deck)
            else:
                print("Playable cards:")
                for i, card in enumerate(playable_cards):
                    print(f"{i + 1}: {card}")

                choice = int(input("Choose a card to play (enter the number): ")) - 1  #######
                chosen_card = playable_cards[choice]  #######
                player.play_card(chosen_card, self.current_card)
                self.current_card = chosen_card
                self.deck.insert_to_bounce_deck(chosen_card)
            # self.next_player()
            break

    def _handle_card_seven(self):
        self.next_player()
        self.players[self.current_player_index].draw_card(self.deck)

    def _handle_card_eight(self):
        self.next_player()
        player = self.players[self.current_player_index]
        print(f"\n{player.user_name} skip his turn.")
        self.players[self.current_player_index].draw_card(self.deck)
        self.players[self.current_player_index].draw_card(self.deck)

    def _handle_card_jack(self):
        print("You played a Jack! Choose a suit:")
        for i, suit in enumerate(self.deck.suits):
            print(f"{i + 1}: {suit}")

        choice = int(input("Choose a suit (enter the number): ")) - 1

        self.chosen_suit = self.deck.suits[choice]
        print(f"The chosen suit is now {self.chosen_suit}")

    def _handle_card_ace(self):
        self.next_player()
        player = self.players[self.current_player_index]
        print(f"\n{player.user_name} skip his turn.")

    def handle_special_cards(self, player: Player):
        match self.current_card.rank:
            case "6":
                self._handle_card_six(player=player)
            case "7":
                self._handle_card_seven()
            case "8":
                self._handle_card_eight()
            case "J":
                self._handle_card_jack()
            case "A":
                self._handle_card_ace()
