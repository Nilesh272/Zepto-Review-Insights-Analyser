"""Load `.env` from the project root into process environment (no-op if missing)."""

from __future__ import annotations

from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env(*, override: bool = False) -> Path | None:
    """Load ``phase-7-orchestration/.env`` if present. Returns the path loaded, or None."""
    env_path = _PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return None
    try:
        from dotenv import load_dotenv  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "Found a .env file but python-dotenv is not installed. "
            "Run: pip install python-dotenv"
        ) from exc
    load_dotenv(env_path, override=override)
    return env_path
