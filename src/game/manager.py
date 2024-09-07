import random
from typing import List, Optional

from src.connection.manager import ConnectionManager
from src.user.models import Player


class GameManager:
    def __init__(self, manager: ConnectionManager):
        self.connection_manager = manager
        self.games = {}  # Ключ — это game_id, значение — список игроков

    def create_game(self, game_id: str, players: List[Player]):
        self.games[game_id] = players

    def get_players(self, game_id: str) -> List[Player]:
        return self.games.get(game_id, [])

    def remove_game(self, game_id: str):
        if game_id in self.games:
            del self.games[game_id]

    def get_player_or_none(self, game_id: str, user_id: str) -> Optional[Player]:
        players = self.get_players(game_id)
        for player in players:
            if player.user_id == user_id:  # Проверяем, совпадает ли user_id
                return player
        return None



# class Game:
#     def __init__(self, players: List[Player]):
#         self.deck = Deck()
#         self.players = players
#         self.current_card = self.deck.draw_card()
#         self.current_player_index = 0
#         self.direction = 1  # 1 для вперед, -1 для назад
#
#         # Вытягиваем карты для каждого игрока
#         for player in self.players:
#             for _ in range(7):
#                 player.draw_card(self.deck)
#
#     def next_player(self):
#         self.current_player_index = (self.current_player_index + self.direction) % len(self.players)
#
#     def play(self):
#         while True:
#             player = self.players[self.current_player_index]
#             print(f"\n{player.name}'s turn. Current card: {self.current_card}")
#             print(f"Hand: {', '.join(str(card) for card in player.hand)}")
#
#             if player.name == "Вы":  # Интерфейс для человеческого игрока
#                 self.human_turn(player)
#             else:
#                 self.computer_turn(player)
#
#             if player.has_won():
#                 print(f"{player.name} has won the game!")
#                 break
#
#             self.next_player()
#
#     def human_turn(self, player):
#         playable_cards = [card for card in player.hand if card.can_play_on(self.current_card)]
#         if not playable_cards:
#             print(f"{player.name} has no playable cards, drawing a card.")
#             player.draw_card(self.deck)
#         else:
#             print("Playable cards:")
#             for i, card in enumerate(playable_cards):
#                 print(f"{i + 1}: {card}")
#
#             choice = int(input("Choose a card to play (enter the number): ")) - 1
#             chosen_card = playable_cards[choice]
#             player.play_card(chosen_card, self.current_card)
#             self.current_card = chosen_card
#
#
#     def computer_turn(self, player):
#         playable_cards = [card for card in player.hand if card.can_play_on(self.current_card)]
#         if not playable_cards:
#             print(f"{player.name} has no playable cards, drawing a card.")
#             player.draw_card(self.deck)
#         else:
#             chosen_card = playable_cards[0]
#             print(f"{player.name} plays {chosen_card}")
#             player.play_card(chosen_card, self.current_card)
#             self.current_card = chosen_card
#
#
#     def handle_special_cards(self):
#         if self.current_card.value == "skip":
#             self.next_player()  # Пропуск следующего игрока
#         elif self.current_card.value == "reverse":
#             self.direction *= -1  # Изменение направления игры
#         elif self.current_card.value == "draw_two":
#             self.next_player()
#             self.players[self.current_player_index].draw_card(self.deck)
#             self.players[self.current_player_index].draw_card(self.deck)
#         elif self.current_card.value == "wild_draw_four":
#             self.next_player()
#             for _ in range(4):
#                 self.players[self.current_player_index].draw_card(self.deck)