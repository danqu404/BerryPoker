"""Application configuration."""

import os
from pathlib import Path

# Server settings
HOST = os.getenv("BERRYPOKER_HOST", "0.0.0.0")
PORT = int(os.getenv("BERRYPOKER_PORT", "8080"))

# CORS settings - comma-separated list of allowed origins
# Example: "https://berrypoker.com,https://www.berrypoker.com"
CORS_ORIGINS = os.getenv("BERRYPOKER_CORS_ORIGINS", "*").split(",")
CORS_ALLOW_ALL = os.getenv("BERRYPOKER_CORS_ORIGINS", "*") == "*"

# Database settings
DATABASE_PATH = Path(os.getenv(
    "BERRYPOKER_DATABASE_PATH",
    str(Path(__file__).parent / "berrypoker.db")
))

# Room settings
ROOM_CLEANUP_HOURS = int(os.getenv("BERRYPOKER_ROOM_CLEANUP_HOURS", "24"))
ROOM_PERSIST_INTERVAL_SECONDS = int(os.getenv("BERRYPOKER_PERSIST_INTERVAL", "30"))

# Production mode
PRODUCTION = os.getenv("BERRYPOKER_PRODUCTION", "false").lower() == "true"

# Debug mode
DEBUG = os.getenv("BERRYPOKER_DEBUG", "false").lower() == "true"
