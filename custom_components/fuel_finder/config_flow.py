"""Config flow for the Fuel Finder integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import FuelFinderAPI, FuelFinderAuthError, FuelFinderConnectionError, FuelFinderRateLimitError
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_STATIONS, DOMAIN, LOGGER
from .models import StationInfo


class FuelFinderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fuel Finder."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client_id: str = ""
        self._client_secret: str = ""
        self._api: FuelFinderAPI | None = None
        self._all_stations: list[StationInfo] = []
        self._filtered_stations: list[StationInfo] = []
        self._selected_stations: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Handle the credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._client_id = user_input[CONF_CLIENT_ID]
            self._client_secret = user_input[CONF_CLIENT_SECRET]

            session = async_get_clientsession(self.hass)
            self._api = FuelFinderAPI(session, self._client_id, self._client_secret)

            try:
                await self._api.authenticate()
            except FuelFinderAuthError:
                errors["base"] = "invalid_auth"
            except FuelFinderRateLimitError:
                errors["base"] = "rate_limited"
            except (FuelFinderConnectionError, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown"
            else:
                return await self.async_step_search()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                    vol.Required(CONF_CLIENT_SECRET): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Handle the station search step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input.get("search_query", "").strip().lower()

            # Fetch all stations on first search
            if not self._all_stations:
                try:
                    raw = await self._api.get_all_stations()
                    self._all_stations = [StationInfo.from_api(s) for s in raw]
                except (FuelFinderAuthError, FuelFinderConnectionError, FuelFinderRateLimitError, aiohttp.ClientError, TimeoutError):
                    LOGGER.exception("Failed to fetch stations")
                    errors["base"] = "cannot_connect"
                    return self.async_show_form(
                        step_id="search",
                        data_schema=self._build_search_schema(),
                        errors=errors,
                    )

            # Filter stations
            self._filtered_stations = [
                s
                for s in self._all_stations
                if query in s.trading_name.lower()
                or query in s.brand_name.lower()
                or query in s.location.postcode.lower()
                or query in s.location.city.lower()
            ]

            if not self._filtered_stations:
                errors["base"] = "no_stations_found"
            else:
                return await self.async_step_select_stations()

        return self.async_show_form(
            step_id="search",
            data_schema=self._build_search_schema(),
            errors=errors,
        )

    async def async_step_select_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Handle the station selection step."""
        if user_input is not None:
            selected = user_input.get("stations", [])
            search_again = user_input.get("search_again", False)

            if selected:
                self._selected_stations.extend(selected)

            if search_again:
                return await self.async_step_search()

            if not self._selected_stations:
                return self.async_show_form(
                    step_id="select_stations",
                    data_schema=self._build_select_schema(),
                    errors={"base": "no_stations_selected"},
                )

            await self.async_set_unique_id(self._client_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Fuel Finder",
                data={
                    CONF_CLIENT_ID: self._client_id,
                    CONF_CLIENT_SECRET: self._client_secret,
                    CONF_STATIONS: self._selected_stations,
                },
            )

        return self.async_show_form(
            step_id="select_stations",
            data_schema=self._build_select_schema(),
        )

    @staticmethod
    def _build_search_schema() -> vol.Schema:
        """Build the schema for station search."""
        return vol.Schema(
            {
                vol.Required("search_query"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }
        )

    def _build_select_schema(self) -> vol.Schema:
        """Build the schema for station selection."""
        options = [
            SelectOptionDict(
                value=s.node_id,
                label=f"{s.trading_name} — {s.location.postcode} ({s.brand_name})",
            )
            for s in self._filtered_stations
        ]
        return vol.Schema(
            {
                vol.Required("stations"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional("search_again", default=False): bool,
            }
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> dict:
        """Handle reauth trigger."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Handle reauth credential entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = FuelFinderAPI(
                session,
                user_input[CONF_CLIENT_ID],
                user_input[CONF_CLIENT_SECRET],
            )
            try:
                await api.authenticate()
            except FuelFinderAuthError:
                errors["base"] = "invalid_auth"
            except FuelFinderRateLimitError:
                errors["base"] = "rate_limited"
            except (FuelFinderConnectionError, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error during re-authentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                        CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                    vol.Required(CONF_CLIENT_SECRET): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Handle reconfiguration."""
        entry = self._get_reconfigure_entry()
        self._client_id = entry.data[CONF_CLIENT_ID]
        self._client_secret = entry.data[CONF_CLIENT_SECRET]
        self._selected_stations = list(entry.data.get(CONF_STATIONS, []))

        session = async_get_clientsession(self.hass)
        self._api = FuelFinderAPI(session, self._client_id, self._client_secret)

        try:
            await self._api.authenticate()
        except (FuelFinderAuthError, FuelFinderConnectionError, FuelFinderRateLimitError, aiohttp.ClientError, TimeoutError):
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_reconfigure_search()

    async def async_step_reconfigure_search(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Handle the station search step during reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input.get("search_query", "").strip().lower()

            if not self._all_stations:
                try:
                    raw = await self._api.get_all_stations()
                    self._all_stations = [StationInfo.from_api(s) for s in raw]
                except (FuelFinderAuthError, FuelFinderConnectionError, FuelFinderRateLimitError, aiohttp.ClientError, TimeoutError):
                    LOGGER.exception("Failed to fetch stations during reconfigure")
                    errors["base"] = "cannot_connect"
                    return self.async_show_form(
                        step_id="reconfigure_search",
                        data_schema=self._build_search_schema(),
                        errors=errors,
                    )

            self._filtered_stations = [
                s
                for s in self._all_stations
                if query in s.trading_name.lower()
                or query in s.brand_name.lower()
                or query in s.location.postcode.lower()
                or query in s.location.city.lower()
            ]

            if not self._filtered_stations:
                errors["base"] = "no_stations_found"
            else:
                return await self.async_step_reconfigure_select()

        return self.async_show_form(
            step_id="reconfigure_search",
            data_schema=self._build_search_schema(),
            errors=errors,
        )

    async def async_step_reconfigure_select(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Handle station selection during reconfiguration."""
        if user_input is not None:
            selected = user_input.get("stations", [])
            search_again = user_input.get("search_again", False)

            if selected:
                for s in selected:
                    if s not in self._selected_stations:
                        self._selected_stations.append(s)

            if search_again:
                return await self.async_step_reconfigure_search()

            if not self._selected_stations:
                return self.async_show_form(
                    step_id="reconfigure_select",
                    data_schema=self._build_select_schema(),
                    errors={"base": "no_stations_selected"},
                )

            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates={CONF_STATIONS: self._selected_stations},
            )

        return self.async_show_form(
            step_id="reconfigure_select",
            data_schema=self._build_select_schema(),
        )
