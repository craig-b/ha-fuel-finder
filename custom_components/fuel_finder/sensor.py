"""Sensor platform for the Fuel Finder integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FUEL_TYPES
from .coordinator import FuelFinderCoordinator
from .models import FuelFinderData


def _build_fuel_descriptions() -> dict[str, SensorEntityDescription]:
    """Build sensor descriptions for each fuel type."""
    return {
        key: SensorEntityDescription(
            key=key,
            name=f"{display} price",
            native_unit_of_measurement="p/L",
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        )
        for key, display in FUEL_TYPES.items()
    }


FUEL_DESCRIPTIONS = _build_fuel_descriptions()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fuel Finder sensors."""
    coordinator: FuelFinderCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    # Per-station price sensors
    for node_id, station in coordinator.data.stations.items():
        for fuel_type in station.fuel_types:
            if fuel_type in FUEL_DESCRIPTIONS:
                entities.append(
                    FuelPriceSensor(
                        coordinator,
                        node_id,
                        station.trading_name,
                        station.brand_name,
                        FUEL_DESCRIPTIONS[fuel_type],
                    )
                )

    # Aggregate cheapest sensors
    fuel_types_with_coverage: set[str] = set()
    for station in coordinator.data.stations.values():
        for ft in station.fuel_types:
            if ft in FUEL_TYPES:
                fuel_types_with_coverage.add(ft)

    for fuel_type in fuel_types_with_coverage:
        entities.append(
            CheapestFuelSensor(coordinator, entry.entry_id, fuel_type)
        )

    async_add_entities(entities)


class FuelPriceSensor(CoordinatorEntity[FuelFinderCoordinator], SensorEntity):
    """Sensor for a fuel price at a specific station."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FuelFinderCoordinator,
        node_id: str,
        trading_name: str,
        brand_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._node_id = node_id
        self._attr_unique_id = f"{node_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, node_id)},
            name=trading_name,
            manufacturer=brand_name,
            model="Petrol Station",
        )

    @property
    def native_value(self) -> float | None:
        """Return the current fuel price."""
        prices = self.coordinator.data.prices.get(self._node_id, [])
        for price in prices:
            if price.fuel_type == self.entity_description.key:
                return price.price
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | None] | None:
        """Return extra state attributes."""
        prices = self.coordinator.data.prices.get(self._node_id, [])
        for price in prices:
            if price.fuel_type == self.entity_description.key:
                return {
                    "price_last_updated": price.price_last_updated,
                    "price_change_effective_timestamp": price.price_change_effective_timestamp,
                }
        return None


class CheapestFuelSensor(CoordinatorEntity[FuelFinderCoordinator], SensorEntity):
    """Sensor for the cheapest fuel price across tracked stations."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FuelFinderCoordinator,
        entry_id: str,
        fuel_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._fuel_type = fuel_type
        display_name = FUEL_TYPES[fuel_type]
        self._attr_unique_id = f"{entry_id}_cheapest_{fuel_type}"
        self.entity_description = SensorEntityDescription(
            key=f"cheapest_{fuel_type}",
            name=f"Cheapest {display_name}",
            native_unit_of_measurement="p/L",
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Fuel Finder",
            model="Price Comparison",
        )

    def _get_sorted_prices(self) -> list[dict]:
        """Get all prices for this fuel type sorted by price."""
        results = []
        for node_id, prices in self.coordinator.data.prices.items():
            station = self.coordinator.data.stations.get(node_id)
            if not station:
                continue
            for price in prices:
                if price.fuel_type == self._fuel_type:
                    loc = station.location
                    address = loc.address_line_1
                    if loc.postcode:
                        address = f"{address}, {loc.postcode}"
                    results.append(
                        {
                            "name": station.trading_name,
                            "price": price.price,
                            "address": address,
                        }
                    )
        results.sort(key=lambda x: x["price"])
        return results

    @property
    def native_value(self) -> float | None:
        """Return the cheapest price."""
        sorted_prices = self._get_sorted_prices()
        if sorted_prices:
            return sorted_prices[0]["price"]
        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return extra state attributes."""
        sorted_prices = self._get_sorted_prices()
        if not sorted_prices:
            return None

        attrs: dict = {
            "station_name": sorted_prices[0]["name"],
            "station_address": sorted_prices[0]["address"],
        }
        if len(sorted_prices) > 1:
            attrs["runner_up_price"] = sorted_prices[1]["price"]
            attrs["runner_up_station"] = sorted_prices[1]["name"]
        attrs["cheapest_3"] = sorted_prices[:3]
        return attrs
