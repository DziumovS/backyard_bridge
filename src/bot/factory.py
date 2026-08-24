import secrets
from collections.abc import Callable, Sequence

from src.bot.models import BotUser


AMERICAN_NAMES = (
    "Alex",
    "Avery",
    "Benjamin",
    "Cameron",
    "Charlie",
    "Daniel",
    "Ethan",
    "Grace",
    "Hannah",
    "Jackson",
    "James",
    "Logan",
    "Lucas",
    "Madison",
    "Mason",
    "Noah",
    "Olivia",
    "Riley",
    "Sophia",
    "Taylor",
)


class BotFactory:
    def __init__(
        self,
        names: Sequence[str] = AMERICAN_NAMES,
        chooser: Callable[[Sequence[str]], str] = secrets.choice,
    ):
        self.names = tuple(names)
        self.chooser = chooser

    def create(self, existing_names: set[str] | None = None) -> BotUser:
        existing_names = existing_names or set()
        available_names = [name for name in self.names if f"{name} Bot" not in existing_names]
        first_name = self.chooser(available_names or self.names)
        return BotUser(
            user_id=f"bot-{secrets.token_urlsafe(9)}",
            user_name=f"{first_name} Bot",
        )
