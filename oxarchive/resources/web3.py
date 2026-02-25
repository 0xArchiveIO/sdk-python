"""Web3 authentication resource — wallet-based API key management via SIWE."""

from __future__ import annotations

from ..http import HttpClient
from ..types import (
    OxArchiveError,
    SiweChallenge,
    Web3KeysList,
    Web3PaymentRequired,
    Web3RevokeResult,
    Web3SignupResult,
    Web3SubscribeResult,
)


class Web3Resource:
    """
    Wallet-based authentication: get API keys via SIWE signature.

    No API key is required for these endpoints. Use an Ethereum wallet to
    create a free-tier account, list keys, or revoke keys — all programmatically.

    Example:
        >>> from oxarchive import Client
        >>>
        >>> client = Client(api_key="placeholder")
        >>>
        >>> # Step 1: Get a challenge
        >>> challenge = client.web3.challenge("0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18")
        >>> print(challenge.message)  # Sign this with personal_sign
        >>>
        >>> # Step 2: Sign the message with your wallet, then submit
        >>> result = client.web3.signup(message=challenge.message, signature="0x...")
        >>> print(f"API key: {result.api_key}")
    """

    def __init__(self, http: HttpClient):
        self._http = http

    def challenge(self, address: str) -> SiweChallenge:
        """Get a SIWE challenge message to sign.

        Args:
            address: Ethereum wallet address.

        Returns:
            SIWE message and nonce. Sign the message with personal_sign (EIP-191).
        """
        data = self._http.post("/v1/auth/web3/challenge", json={"address": address})
        return SiweChallenge(**data)

    async def achallenge(self, address: str) -> SiweChallenge:
        """Async version of :meth:`challenge`."""
        data = await self._http.apost("/v1/auth/web3/challenge", json={"address": address})
        return SiweChallenge(**data)

    def signup(self, message: str, signature: str) -> Web3SignupResult:
        """Create a free-tier account and get an API key.

        Args:
            message: The SIWE message from :meth:`challenge`.
            signature: Hex-encoded signature from personal_sign.

        Returns:
            API key, tier, and wallet address.
        """
        data = self._http.post("/v1/web3/signup", json={"message": message, "signature": signature})
        return Web3SignupResult(**data)

    async def asignup(self, message: str, signature: str) -> Web3SignupResult:
        """Async version of :meth:`signup`."""
        data = await self._http.apost("/v1/web3/signup", json={"message": message, "signature": signature})
        return Web3SignupResult(**data)

    def list_keys(self, message: str, signature: str) -> Web3KeysList:
        """List all API keys for the authenticated wallet.

        Args:
            message: The SIWE message from :meth:`challenge`.
            signature: Hex-encoded signature from personal_sign.

        Returns:
            List of API keys and wallet address.
        """
        data = self._http.post("/v1/web3/keys", json={"message": message, "signature": signature})
        return Web3KeysList(**data)

    async def alist_keys(self, message: str, signature: str) -> Web3KeysList:
        """Async version of :meth:`list_keys`."""
        data = await self._http.apost("/v1/web3/keys", json={"message": message, "signature": signature})
        return Web3KeysList(**data)

    def revoke_key(self, message: str, signature: str, key_id: str) -> Web3RevokeResult:
        """Revoke a specific API key.

        Args:
            message: The SIWE message from :meth:`challenge`.
            signature: Hex-encoded signature from personal_sign.
            key_id: UUID of the key to revoke.

        Returns:
            Confirmation message and wallet address.
        """
        data = self._http.post(
            "/v1/web3/keys/revoke",
            json={"message": message, "signature": signature, "key_id": key_id},
        )
        return Web3RevokeResult(**data)

    async def arevoke_key(self, message: str, signature: str, key_id: str) -> Web3RevokeResult:
        """Async version of :meth:`revoke_key`."""
        data = await self._http.apost(
            "/v1/web3/keys/revoke",
            json={"message": message, "signature": signature, "key_id": key_id},
        )
        return Web3RevokeResult(**data)

    def subscribe_quote(self, tier: str) -> Web3PaymentRequired:
        """Get pricing info for a paid subscription (x402 flow, step 1).

        Returns the payment details needed to sign a USDC transfer on Base.
        After signing, pass the payment signature to :meth:`subscribe`.

        Args:
            tier: Subscription tier ('build' or 'pro').

        Returns:
            Payment details (amount, asset, network, pay-to address).
        """
        response = self._http.client.post(
            "/v1/web3/subscribe", json={"tier": tier}
        )
        data = response.json()
        if response.status_code == 402:
            return Web3PaymentRequired(**data.get("payment", data))
        raise OxArchiveError(
            data.get("error", f"Unexpected status {response.status_code}"),
            response.status_code,
        )

    async def asubscribe_quote(self, tier: str) -> Web3PaymentRequired:
        """Async version of :meth:`subscribe_quote`."""
        response = await self._http.async_client.post(
            "/v1/web3/subscribe", json={"tier": tier}
        )
        data = response.json()
        if response.status_code == 402:
            return Web3PaymentRequired(**data.get("payment", data))
        raise OxArchiveError(
            data.get("error", f"Unexpected status {response.status_code}"),
            response.status_code,
        )

    def subscribe(self, tier: str, payment_signature: str) -> Web3SubscribeResult:
        """Complete a paid subscription with a signed x402 payment (step 2).

        Requires a payment signature from signing a USDC transfer (EIP-3009)
        for the amount returned by :meth:`subscribe_quote`.

        Args:
            tier: Subscription tier ('build' or 'pro').
            payment_signature: Signed x402 payment (from EIP-3009 USDC transfer on Base).

        Returns:
            API key, tier, expiration, and wallet address.
        """
        response = self._http.client.post(
            "/v1/web3/subscribe",
            json={"tier": tier},
            headers={"payment-signature": payment_signature},
        )
        data = response.json()
        if not response.is_success:
            raise OxArchiveError(
                data.get("error", "Subscribe failed"), response.status_code
            )
        return Web3SubscribeResult(**data)

    async def asubscribe(self, tier: str, payment_signature: str) -> Web3SubscribeResult:
        """Async version of :meth:`subscribe`."""
        response = await self._http.async_client.post(
            "/v1/web3/subscribe",
            json={"tier": tier},
            headers={"payment-signature": payment_signature},
        )
        data = response.json()
        if not response.is_success:
            raise OxArchiveError(
                data.get("error", "Subscribe failed"), response.status_code
            )
        return Web3SubscribeResult(**data)
