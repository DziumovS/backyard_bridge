import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:8000",
    "http://127.0.0.1:8000",
)


def get_allowed_origins(value: str | None = None) -> list[str]:
    configured = value if value is not None else os.getenv("BACKYARD_BRIDGE_ALLOWED_ORIGINS", "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or list(DEFAULT_ALLOWED_ORIGINS)


def get_reconnect_grace_seconds(value: str | None = None) -> float:
    configured = value if value is not None else os.getenv("BACKYARD_BRIDGE_RECONNECT_GRACE_SECONDS", "60")
    try:
        return max(0.0, float(configured))
    except ValueError:
        return 60.0


def use_dev_assets(value: str | None = None) -> bool:
    configured = value if value is not None else os.getenv("BACKYARD_BRIDGE_DEV_ASSETS", "")
    return configured.strip().lower() in {"1", "true", "yes"}
