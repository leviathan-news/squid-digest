#!/usr/bin/env python3
"""Place prediction market trades via Telegram commands in the Agent Chat.

Sends /buy commands to t.me/leviathan_agents so the squid-bot processes them.

Usage:
    uv run python scripts/place_predictions.py --dry-run
    uv run python scripts/place_predictions.py
"""

import argparse
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx

from squid_digest.telegram import TelegramClient
from squid_digest.agents_chat import AgentsChatClient


def send_and_register(client, relay, chat_id, topic_id, text):
    """Send a message via Telegram Bot API, then register with Leviathan relay."""
    # Step 1: Send via Telegram Bot API (preserves bot identity)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "message_thread_id": topic_id,
    }
    with httpx.Client(timeout=30) as http:
        resp = http.post(f"{client.api_url}/sendMessage", json=payload)
        resp.raise_for_status()
        result = resp.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram send failed: {result}")

    msg_id = result["result"]["message_id"]

    # Step 2: Register with Leviathan relay (for history/search visibility)
    try:
        relay_result = relay.register_post(
            text=text,
            topic_id=topic_id,
            telegram_message_id=msg_id,
        )
        return msg_id, relay_result
    except Exception as e:
        print(f"⚠ Relay registration failed (non-fatal): {e}")
        return msg_id, None


def main():
    parser = argparse.ArgumentParser(description="Place prediction market trades via Telegram")
    parser.add_argument("--dry-run", action="store_true", help="Preview commands without sending")
    args = parser.parse_args()

    # Trades: (market_id, outcome, amount, rationale)
    trades = [
        (1, "no", 100, "Kill rate >40% — NO. Market at 0.90 YES, contrarian bet."),
        (2, "no", 50, "10 active participants by Friday — SOFT NO. Market already agrees, small size."),
        (3, "yes", 100, "50+ yaps on an article — YES. Market at 0.50, even odds."),
    ]

    chat_id = os.getenv("LEVIATHAN_AGENTS_CHAT_ID")
    topic_id = int(os.getenv("LEVIATHAN_AGENTS_TOPIC_ID", "154"))

    if not chat_id:
        print("ERROR: LEVIATHAN_AGENTS_CHAT_ID not set")
        sys.exit(1)

    print("Prediction market trades to place:\n")
    for market_id, outcome, amount, rationale in trades:
        cmd = f"/buy {market_id} {outcome} {amount}"
        print(f"  {cmd}  — {rationale}")

    if args.dry_run:
        print("\n✓ Dry run complete. Remove --dry-run to send.")
        return

    client = TelegramClient(require_channel=False)
    relay = AgentsChatClient()

    print()
    for market_id, outcome, amount, rationale in trades:
        cmd = f"/buy {market_id} {outcome} {amount}"
        print(f"Sending: {cmd} ...", end=" ")
        try:
            msg_id, relay_result = send_and_register(client, relay, chat_id, topic_id, cmd)
            relay_status = "relay ✓" if relay_result else "relay ⚠"
            print(f"✓ (message_id: {msg_id}, {relay_status})")
        except Exception as e:
            print(f"✗ {e}")

        # Small delay between trades to avoid rate limiting
        time.sleep(2)

    print("\n✓ All trades sent.")


if __name__ == "__main__":
    main()
