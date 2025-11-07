"""Telegram bot service module for Squid Digest."""

from .client import TelegramClient
from .formatter import format_for_telegram

__all__ = ["TelegramClient", "format_for_telegram"]

