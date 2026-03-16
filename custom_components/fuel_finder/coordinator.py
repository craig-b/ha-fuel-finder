"""Data update coordinator for the Fuel Finder integration."""

from __future__ import annotations

from datetime import UTC, datetime

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FuelFinderAPI, FuelFinderAuthError, FuelFinderConnectionError, FuelFinderRateLimitError
from .const import DOMAIN, LOGGER, UPDATE_INTERVAL
from .models import FuelFinderData, FuelPrice, StationInfo


class FuelFinderCoordinator(DataUpdateCoordinator[FuelFinderData]):
    """Coordinator for fetching fuel price data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FuelFinderAPI,
        tracked_stations: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.tracked_stations = set(tracked_stations)
        self._last_fetch_timestamp: str | None = None
        self._station_cache: dict[str, StationInfo] = {}
        self._price_cache: dict[str, list[FuelPrice]] = {}

    async def _async_update_data(self) -> FuelFinderData:
        """Fetch data from the API."""
        try:
            async with async_timeout.timeout(120):
                if self._last_fetch_timestamp is None:
                    await self._full_fetch()
                else:
                    await self._incremental_fetch()
        except FuelFinderAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except FuelFinderRateLimitError as err:
            raise UpdateFailed(f"Rate limited: {err}") from err
        except FuelFinderConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

        self._last_fetch_timestamp = datetime.now(UTC).strftime("%Y-%m-%d")

        return FuelFinderData(
            stations=dict(self._station_cache),
            prices=dict(self._price_cache),
            last_fetch_timestamp=self._last_fetch_timestamp,
        )

    async def _full_fetch(self) -> None:
        """Perform initial full data fetch."""
        raw_stations = await self.api.get_all_stations()
        for item in raw_stations:
            node_id = item.get("node_id")
            if node_id in self.tracked_stations:
                self._station_cache[node_id] = StationInfo.from_api(item)

        raw_prices = await self.api.get_all_prices()
        for item in raw_prices:
            node_id = item.get("node_id")
            if node_id in self.tracked_stations:
                self._price_cache[node_id] = [
                    FuelPrice.from_api(p) for p in item.get("fuel_prices", [])
                ]

    async def _incremental_fetch(self) -> None:
        """Fetch incremental updates since last fetch."""
        raw_stations = await self.api.get_incremental_stations(
            self._last_fetch_timestamp
        )
        for item in raw_stations:
            node_id = item.get("node_id")
            if node_id in self.tracked_stations:
                self._station_cache[node_id] = StationInfo.from_api(item)

        raw_prices = await self.api.get_incremental_prices(
            self._last_fetch_timestamp
        )
        for item in raw_prices:
            node_id = item.get("node_id")
            if node_id in self.tracked_stations:
                self._price_cache[node_id] = [
                    FuelPrice.from_api(p) for p in item.get("fuel_prices", [])
                ]
