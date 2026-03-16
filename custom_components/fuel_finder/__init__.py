"""The Fuel Finder integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FuelFinderAPI, FuelFinderAuthError, FuelFinderConnectionError
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_STATIONS, DOMAIN
from .coordinator import FuelFinderCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fuel Finder from a config entry."""
    session = async_get_clientsession(hass)
    api = FuelFinderAPI(
        session,
        entry.data[CONF_CLIENT_ID],
        entry.data[CONF_CLIENT_SECRET],
    )

    try:
        await api.authenticate()
    except FuelFinderAuthError as err:
        raise ConfigEntryAuthFailed(err) from err
    except (FuelFinderConnectionError, TimeoutError) as err:
        raise ConfigEntryNotReady(err) from err

    coordinator = FuelFinderCoordinator(
        hass, api, entry.data[CONF_STATIONS]
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
