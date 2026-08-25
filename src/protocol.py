from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CardPayload(Message):
    rank: Literal["6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    suit: Literal["♠", "♥", "♦", "♣"]


Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=13)]


class CreateLobbyMessage(Message):
    type: Literal["crl"]
    user_name: Username
    is_public: bool = False
    max_players: int = Field(default=4, ge=2, le=4)


class JoinLobbyMessage(Message):
    type: Literal["jl"]
    user_name: Username
    lobby_id: str = Field(pattern=r"^[0-9a-f]{6}$")


class CloseLobbyMessage(Message):
    type: Literal["cll"]
    lobby_id: str | None = None


class StartGameMessage(Message):
    type: Literal["sg"]


class AddBotMessage(Message):
    type: Literal["ab"]


class KickUserMessage(Message):
    type: Literal["ku"]
    user_id: str = Field(min_length=1, max_length=64)


LobbyMessage = Annotated[
    CreateLobbyMessage
    | JoinLobbyMessage
    | CloseLobbyMessage
    | StartGameMessage
    | AddBotMessage
    | KickUserMessage,
    Field(discriminator="type"),
]
lobby_message_adapter = TypeAdapter(LobbyMessage)


class GameStartedMessage(Message):
    type: Literal["gs"]


class GameAuthMessage(Message):
    type: Literal["auth"]
    token: str = Field(min_length=32, max_length=128)


game_auth_adapter = TypeAdapter(GameAuthMessage)


class PlayedCardMessage(Message):
    type: Literal["pc"]
    card: CardPayload
    chosen_suit: Literal["♠", "♥", "♦", "♣"] | None


class DrewCardMessage(Message):
    type: Literal["dc"]


class SkipTurnMessage(Message):
    type: Literal["st"]


class ShowMoveMessage(Message):
    type: Literal["smm"]
    card: CardPayload | None = None


class GameOverMessage(Message):
    type: Literal["go"]


class ResetGameMessage(Message):
    type: Literal["rg"]


GameMessage = Annotated[
    GameStartedMessage
    | PlayedCardMessage
    | DrewCardMessage
    | SkipTurnMessage
    | ShowMoveMessage
    | GameOverMessage
    | ResetGameMessage,
    Field(discriminator="type"),
]
game_message_adapter = TypeAdapter(GameMessage)
