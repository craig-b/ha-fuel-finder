"""API client for the Fuel Finder service."""

from __future__ import annotations

import time

import aiohttp

from .const import LOGGER, PRICES_URL, STATIONS_URL, TOKEN_URL


class FuelFinderAuthError(Exception):
    """Authentication error."""


class FuelFinderConnectionError(Exception):
    """Connection error."""


class FuelFinderRateLimitError(Exception):
    """Rate limit error."""


class FuelFinderAPI:
    """Client for the UK Government Fuel Finder API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: str | None = None
        self._token_expiry: float = 0

    async def authenticate(self) -> None:
        """Authenticate with the API using client credentials."""
        try:
            resp = await self._session.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
        except aiohttp.ClientError as err:
            raise FuelFinderConnectionError(
                f"Failed to connect to token endpoint: {err}"
            ) from err

        if resp.status in (400, 403):
            raise FuelFinderAuthError("Invalid client credentials")
        if resp.status == 429:
            raise FuelFinderRateLimitError("Rate limited during authentication")
        if resp.status in (500, 502, 503, 504):
            raise FuelFinderConnectionError(f"Server error during auth: {resp.status}")
        if resp.status != 200:
            raise FuelFinderConnectionError(f"Unexpected status during auth: {resp.status}")

        data = await resp.json()
        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._token_expiry = time.time() + expires_in - 60  # refresh 60s early

    async def _ensure_token(self) -> None:
        """Ensure we have a valid token."""
        if self._access_token is None or time.time() >= self._token_expiry:
            await self.authenticate()

    async def _request(self, url: str, params: dict | None = None) -> dict:
        """Make an authenticated GET request with retry on 403."""
        await self._ensure_token()

        for attempt in range(2):
            try:
                resp = await self._session.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )
            except aiohttp.ClientError as err:
                raise FuelFinderConnectionError(
                    f"Connection error: {err}"
                ) from err

            if resp.status == 200:
                return await resp.json()

            if resp.status == 403 and attempt == 0:
                LOGGER.debug("Got 403, re-authenticating")
                await self.authenticate()
                continue

            if resp.status == 403:
                raise FuelFinderAuthError("Authentication failed after retry")
            if resp.status == 400:
                raise FuelFinderAuthError(f"Bad request: {resp.status}")
            if resp.status == 429:
                raise FuelFinderRateLimitError("API rate limit exceeded")
            if resp.status in (500, 502, 503, 504):
                raise FuelFinderConnectionError(f"Server error: {resp.status}")

            raise FuelFinderConnectionError(
                f"Unexpected status {resp.status}"
            )

        raise FuelFinderConnectionError("Request failed after retry")

    async def _fetch_all_batches(
        self, url: str, extra_params: dict | None = None
    ) -> list[dict]:
        """Fetch all batches from a paginated endpoint."""
        all_data: list[dict] = []
        batch = 1

        while True:
            params = {"batch-number": batch}
            if extra_params:
                params.update(extra_params)

            result = await self._request(url, params)
            data = result.get("data", [])

            if not data:
                break

            all_data.extend(data)
            batch += 1

        return all_data

    async def get_all_stations(self) -> list[dict]:
        """Fetch all station information."""
        return await self._fetch_all_batches(STATIONS_URL)

    async def get_all_prices(self) -> list[dict]:
        """Fetch all fuel prices."""
        return await self._fetch_all_batches(PRICES_URL)

    async def get_incremental_stations(self, since: str) -> list[dict]:
        """Fetch station updates since a timestamp."""
        return await self._fetch_all_batches(
            STATIONS_URL, {"effective-start-timestamp": since}
        )

    async def get_incremental_prices(self, since: str) -> list[dict]:
        """Fetch price updates since a timestamp."""
        return await self._fetch_all_batches(
            PRICES_URL, {"effective-start-timestamp": since}
        )
