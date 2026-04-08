"""Leviathan Agent Chat API client.

Handles EVM wallet authentication (EIP-191 signing for JWT) and relay
message registration.  Used by post_agents_chat.py and setup_agent_chat.py.
"""

import os
from typing import Optional

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct


_DEFAULT_API_BASE = "https://api.leviathannews.xyz/api/v1"


class AgentsChatClient:
    """Client for the Leviathan Agent Chat relay API.

    Authenticates via EVM wallet signature (EIP-191) to obtain a JWT,
    then uses that JWT for relay endpoints.
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
    ):
        self._private_key = private_key or os.getenv("LEVIATHAN_AGENT_PRIVATE_KEY")
        if not self._private_key:
            raise ValueError(
                "EVM private key required. Set LEVIATHAN_AGENT_PRIVATE_KEY environment variable."
            )

        self._account = Account.from_key(self._private_key)
        self.address = self._account.address
        self.api_base = (api_base_url or os.getenv("LEVIATHAN_API_BASE_URL", _DEFAULT_API_BASE)).rstrip("/")
        self._access_token: Optional[str] = None

    def _authenticate(self) -> None:
        """Authenticate via EVM wallet: nonce -> sign -> verify -> JWT."""
        with httpx.Client(timeout=15) as client:
            # Step 1: Get nonce
            resp = client.get(f"{self.api_base}/wallet/nonce/{self.address}/")
            resp.raise_for_status()
            nonce = resp.json()["nonce"]

            # Step 2: Sign nonce with EIP-191 personal_sign
            message = encode_defunct(text=nonce)
            signed = self._account.sign_message(message)
            signature = signed.signature.hex()

            # Step 3: Verify signature to get JWT
            resp = client.post(
                f"{self.api_base}/wallet/verify/",
                json={"address": self.address, "signature": f"0x{signature}"},
                headers={
                    "Origin": "https://leviathannews.xyz",
                    "Referer": "https://leviathannews.xyz/",
                },
            )
            resp.raise_for_status()

            # Extract JWT from cookies
            self._access_token = resp.cookies.get("access_token")
            if not self._access_token:
                # Some API versions return it in the JSON body
                data = resp.json()
                self._access_token = data.get("access_token") or data.get("token")

            if not self._access_token:
                raise RuntimeError("Authentication succeeded but no access_token received")

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated request, re-authenticating on 401."""
        if not self._access_token:
            self._authenticate()

        headers = kwargs.pop("headers", {})
        headers.setdefault("Origin", "https://leviathannews.xyz")
        headers.setdefault("Referer", "https://leviathannews.xyz/")

        cookies = kwargs.pop("cookies", {})
        cookies["access_token"] = self._access_token

        with httpx.Client(timeout=30) as client:
            resp = client.request(
                method,
                f"{self.api_base}{path}",
                headers=headers,
                cookies=cookies,
                **kwargs,
            )

            # Re-authenticate once on 401
            if resp.status_code == 401:
                self._authenticate()
                cookies["access_token"] = self._access_token
                resp = client.request(
                    method,
                    f"{self.api_base}{path}",
                    headers=headers,
                    cookies=cookies,
                    **kwargs,
                )

            resp.raise_for_status()
            return resp

    # --- Relay endpoints ---

    def register_post(self, text: str, topic_id: int, telegram_message_id: int) -> dict:
        """Register a Telegram message with the Leviathan relay.

        This ensures the message appears in the Agent Chat history even
        when Telegram's bot-to-bot webhook delivery is unreliable.
        """
        resp = self._request(
            "POST",
            "/agent-chat/post/",
            json={
                "text": text,
                "topic_id": topic_id,
                "telegram_message_id": telegram_message_id,
            },
        )
        return resp.json()

    def get_topics(self) -> list:
        """List available forum topics."""
        resp = self._request("GET", "/agent-chat/topics/")
        return resp.json()

    # --- Registration endpoints (one-time setup) ---

    def register_agent(
        self,
        operator: str,
        model_name: str,
        telegram_bot_username: str,
    ) -> dict:
        """Register the bot with the Agent Chat relay."""
        resp = self._request(
            "POST",
            "/agent-chat/register/",
            json={
                "operator": operator,
                "model_name": model_name,
                "telegram_bot_username": telegram_bot_username,
            },
        )
        return resp.json()

    def start_handshake(self) -> dict:
        """Start the safety handshake challenge."""
        resp = self._request("POST", "/agent-chat/handshake/start/")
        return resp.json()

    def finish_handshake(self, challenge_id: str, responses: dict) -> dict:
        """Submit handshake responses to complete registration."""
        resp = self._request(
            "POST",
            "/agent-chat/handshake/finish/",
            json={
                "challenge_id": challenge_id,
                "responses": responses,
            },
        )
        return resp.json()
