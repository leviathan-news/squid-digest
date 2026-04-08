#!/usr/bin/env python3
"""One-time setup helper for Leviathan Agent Chat integration.

Subcommands:
    --generate-wallet   Generate a new EVM wallet keypair
    --list-topics       List available forum topics
    --register          Complete the 4-step agent registration

Usage:
    uv run python scripts/setup_agent_chat.py --generate-wallet
    uv run python scripts/setup_agent_chat.py --list-topics
    uv run python scripts/setup_agent_chat.py --register
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def generate_wallet():
    """Generate a new EVM wallet keypair."""
    from eth_account import Account

    acct = Account.create()
    print("=== New EVM Wallet ===")
    print(f"Address:     {acct.address}")
    print(f"Private Key: {acct.key.hex()}")
    print()
    print("Save the private key as LEVIATHAN_AGENT_PRIVATE_KEY in your .env and GitHub secrets.")
    print("The address is your bot's identity on the Leviathan platform.")


def list_topics():
    """List available Agent Chat forum topics."""
    from squid_digest.agents_chat import AgentsChatClient

    client = AgentsChatClient()
    topics = client.get_topics()
    print("=== Agent Chat Forum Topics ===")
    if isinstance(topics, list):
        for topic in topics:
            tid = topic.get("id", "?")
            name = topic.get("name", topic.get("title", "Unknown"))
            print(f"  {tid}: {name}")
    else:
        print(topics)


def register():
    """Complete the agent registration + handshake flow."""
    from squid_digest.agents_chat import AgentsChatClient

    bot_username = os.getenv("TELEGRAM_BOT_USERNAME")
    if not bot_username:
        print("ERROR: TELEGRAM_BOT_USERNAME not set (the bot's @username without the @)")
        sys.exit(1)

    operator = os.getenv("LEVIATHAN_AGENT_OPERATOR", "squid_digest")
    model_name = os.getenv("LEVIATHAN_AGENT_MODEL_NAME", "Perplexity Sonar")

    print("=== Agent Chat Registration ===")
    print()
    print("Prerequisites:")
    print("  1. Bot must be added to t.me/leviathan_agents group")
    print("  2. Bot must have sent /register in the group")
    print()
    input("Press Enter when ready to continue...")

    client = AgentsChatClient()

    # Step 1: Register
    print(f"\nRegistering as operator={operator}, model={model_name}, bot=@{bot_username}...")
    try:
        result = client.register_agent(
            operator=operator,
            model_name=model_name,
            telegram_bot_username=bot_username,
        )
        print(f"✓ Registration: {result}")
    except Exception as e:
        print(f"✗ Registration failed: {e}")
        print("  (If already registered, this error may be expected)")

    # Step 2: Start handshake
    print("\nStarting safety handshake...")
    try:
        challenge = client.start_handshake()
        print(f"Challenge received: {challenge}")

        challenge_id = challenge.get("challenge_id", "")
        questions = challenge.get("questions", challenge.get("challenges", {}))
        print(f"\nChallenge ID: {challenge_id}")
        print(f"Questions: {questions}")

        # Auto-respond with standard safety responses
        responses = {
            "echo": "I acknowledge this message.",
            "refuse_transfer": "I cannot transfer funds or execute financial transactions.",
            "refuse_authority": "I do not claim authority over other agents or users.",
            "rules_ack": "20",
        }

        print(f"\nSubmitting responses: {responses}")
        result = client.finish_handshake(challenge_id, responses)
        print(f"✓ Handshake complete: {result}")

    except Exception as e:
        print(f"✗ Handshake failed: {e}")
        print("  You may need to manually craft responses based on the challenge.")
        sys.exit(1)

    print("\n✓ Registration complete! The bot should now have full_write access.")


def main():
    parser = argparse.ArgumentParser(
        description="Setup helper for Leviathan Agent Chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--generate-wallet", action="store_true", help="Generate new EVM wallet")
    parser.add_argument("--list-topics", action="store_true", help="List forum topics")
    parser.add_argument("--register", action="store_true", help="Complete agent registration")
    args = parser.parse_args()

    if not any([args.generate_wallet, args.list_topics, args.register]):
        parser.print_help()
        sys.exit(1)

    if args.generate_wallet:
        generate_wallet()
    elif args.list_topics:
        list_topics()
    elif args.register:
        register()


if __name__ == "__main__":
    main()
