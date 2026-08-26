from src.config import DEFAULT_ALLOWED_ORIGINS, get_allowed_origins, get_reconnect_grace_seconds, use_dev_assets


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


def test_reconnect_grace_uses_configured_safe_value(monkeypatch):
    monkeypatch.setenv("BACKYARD_BRIDGE_RECONNECT_GRACE_SECONDS", "12.5")
    assert get_reconnect_grace_seconds() == 12.5
    assert get_reconnect_grace_seconds("-1") == 0
    assert get_reconnect_grace_seconds("invalid") == 60


def test_dev_assets_are_opt_in(monkeypatch):
    monkeypatch.delenv("BACKYARD_BRIDGE_DEV_ASSETS", raising=False)
    assert not use_dev_assets()
    assert use_dev_assets("YES")
    assert not use_dev_assets("no")
