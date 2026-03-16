"""Binary sensor platform for the Fuel Finder integration."""

from __future__ import annotations

from datetime import datetime, time

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import FuelFinderCoordinator

DAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fuel Finder binary sensors."""
    coordinator: FuelFinderCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        StationOpenBinarySensor(coordinator, node_id, station.trading_name, station.brand_name)
        for node_id, station in coordinator.data.stations.items()
    ]
    async_add_entities(entities)


class StationOpenBinarySensor(
    CoordinatorEntity[FuelFinderCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether a station is open."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_has_entity_name = True
    _attr_name = "Open"

    def __init__(
        self,
        coordinator: FuelFinderCoordinator,
        node_id: str,
        trading_name: str,
        brand_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._node_id = node_id
        self._attr_unique_id = f"{node_id}_open"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, node_id)},
            name=trading_name,
            manufacturer=brand_name,
            model="Petrol Station",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the station is open."""
        station = self.coordinator.data.stations.get(self._node_id)
        if station is None:
            return None

        if station.temporary_closure or station.permanent_closure:
            return False

        opening_times = station.opening_times
        usual_days = opening_times.get("usual_days", {})
        if not usual_days:
            return None

        now = dt_util.now()
        day_name = DAY_NAMES[now.weekday()]
        day_info = usual_days.get(day_name)

        if not day_info:
            return None

        if day_info.get("is_24_hours"):
            return True

        open_str = day_info.get("open", "00:00:00")
        close_str = day_info.get("close", "00:00:00")

        # open and close both 00:00:00 with is_24_hours=False means closed
        if open_str == "00:00:00" and close_str == "00:00:00":
            return False

        try:
            open_time = _parse_time(open_str)
            close_time = _parse_time(close_str)
        except ValueError:
            return None

        current_time = now.time()
        return open_time <= current_time < close_time


def _parse_time(time_str: str) -> time:
    """Parse a time string in HH:MM:SS format."""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]), int(parts[2]))
