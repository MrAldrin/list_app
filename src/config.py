import os

from dotenv import load_dotenv

# Local development uses .env; deployment environment variables take precedence.
load_dotenv()


def app_reload_enabled() -> bool:
    """Enable the development file watcher only for an explicit true value."""
    return os.environ.get("APP_RELOAD", "false").strip().lower() == "true"


def require_app_password() -> str:
    password = os.environ.get("APP_PASSWORD")
    if password is None or not password.strip():
        raise RuntimeError(
            "APP_PASSWORD must be set and not blank. "
            "Set it in your local .env file or Railway environment variables "
            "before starting the app."
        )
    # Check for whitespace-only values without changing the actual password.
    return password
