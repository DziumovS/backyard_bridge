from src.config import DEFAULT_ALLOWED_ORIGINS, get_allowed_origins


def test_allowed_origins_use_safe_defaults(monkeypatch):
    monkeypatch.delenv("BACKYARD_BRIDGE_ALLOWED_ORIGINS", raising=False)
    assert get_allowed_origins() == list(DEFAULT_ALLOWED_ORIGINS)
    assert get_allowed_origins(" , ") == list(DEFAULT_ALLOWED_ORIGINS)


def test_allowed_origins_parse_environment(monkeypatch):
    monkeypatch.setenv(
        "BACKYARD_BRIDGE_ALLOWED_ORIGINS",
        " https://game.example,https://mobile.example, ",
    )
    assert get_allowed_origins() == [
        "https://game.example",
        "https://mobile.example",
    ]
