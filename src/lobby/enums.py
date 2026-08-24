from enum import Enum

class EventType(Enum):
    SESSION = "sid"
    SHOW_ERROR = "se"
    TOGGLE_START_BUTTON = "tsb"
    LOBBY_CREATED = "lcr"
    USERS_UPDATE = "uu"
    JOINED_LOBBY = "jdl"
    START_GAME = "sg"
    LOBBY_CLOSED = "lcl"
    CREATE_LOBBY = "crl"
    CLOSE_LOBBY = "cll"
    JOIN_LOBBY = "jl"
    ADD_BOT = "ab"
    KICK_USER = "ku"
    KICKED_FROM_LOBBY = "kfl"
