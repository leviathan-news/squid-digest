"""Configuration management for Squid Digest."""
import os
from pathlib import Path
from dotenv import load_dotenv


# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Application configuration loaded from environment variables."""

    # API Configuration
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
    GHOST_URL = os.getenv("GHOST_URL")
    GHOST_ADMIN_API_KEY = os.getenv("GHOST_ADMIN_API_KEY")

    @classmethod
    def validate(cls):
        """Validate that required environment variables are set."""
        required = {
            "PERPLEXITY_API_KEY": cls.PERPLEXITY_API_KEY,
            "GHOST_URL": cls.GHOST_URL,
            "GHOST_ADMIN_API_KEY": cls.GHOST_ADMIN_API_KEY,
        }

        missing = [key for key, value in required.items() if not value]

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Please set them in your .env file"
            )


# Global config instance
config = Config()
