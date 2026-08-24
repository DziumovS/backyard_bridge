from collections import Counter

from src.deck.models import Card
from src.user.models import Player


class BotStrategy:
    """A deterministic, offensive strategy focused on emptying the bot's hand."""

    _rank_priority = {
        "J": 90,
        "A": 80,
        "8": 70,
        "7": 60,
        "10": 50,
        "Q": 50,
        "K": 50,
        "9": 20,
        "6": 10,
    }
    _suits = ("♠", "♥", "♦", "♣")

    def playable_cards(self, game, player: Player) -> list[Card]:
        jack_chain = (
            game.current_card.rank == "J"
            and game.chosen_suit
            and game.chosen_suit["chooser_id"] == player.user_id
        )
        return player.get_playable_cards(
            current_card=game.current_card,
            chosen_suit=None if jack_chain else game.chosen_suit,
            j=bool(jack_chain),
        )

    def choose_card(self, game, player: Player) -> Card | None:
        playable = self.playable_cards(game, player)
        if not playable:
            return None

        suit_counts = Counter(card.suit for card in player.hand)

        def value(card: Card) -> tuple[int, int, int, str, str]:
            wins_round = int(len(player.hand) == 1 and card.rank != "6")
            return (
                wins_round,
                self._rank_priority[card.rank],
                suit_counts[card.suit],
                card.rank,
                card.suit,
            )

        return max(playable, key=value)

    def choose_suit(self, player: Player, played_card: Card) -> str:
        remaining_suits = Counter(card.suit for card in player.hand if card is not played_card)
        return max(self._suits, key=lambda suit: (remaining_suits[suit], -self._suits.index(suit)))

    @staticmethod
    def should_call_bridge(game, player: Player) -> bool:
        return game.bridge_pending_for == player.user_id
