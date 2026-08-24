from src.user.models import Player, User


class BotUser(User):
    is_bot = True

    def __init__(self, user_id: str, user_name: str):
        super().__init__(user_id=user_id, websocket=None, user_name=user_name)


class BotPlayer(Player):
    is_bot = True

    def __init__(self, user_id: str, user_name: str, session_token: str | None = None):
        super().__init__(
            user_id=user_id,
            websocket=None,
            user_name=user_name,
            session_token=session_token,
        )

    @classmethod
    def from_user(cls, user: BotUser) -> "BotPlayer":
        return cls(user.user_id, user.user_name, user.session_token)
