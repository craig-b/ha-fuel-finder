"""Data models for the Fuel Finder integration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StationLocation:
    """Station location data."""

    address_line_1: str
    address_line_2: str | None
    city: str
    country: str
    county: str | None
    postcode: str
    latitude: float
    longitude: float


@dataclass
class StationInfo:
    """Station information."""

    node_id: str
    trading_name: str
    brand_name: str
    location: StationLocation
    amenities: list[str]
    opening_times: dict
    fuel_types: list[str]
    temporary_closure: bool
    permanent_closure: bool
    is_motorway_service_station: bool
    is_supermarket_service_station: bool
    public_phone_number: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> StationInfo:
        """Create a StationInfo from API response data."""
        loc = data.get("location", {})
        return cls(
            node_id=data["node_id"],
            trading_name=data.get("trading_name", ""),
            brand_name=data.get("brand_name", ""),
            location=StationLocation(
                address_line_1=loc.get("address_line_1", ""),
                address_line_2=loc.get("address_line_2"),
                city=loc.get("city", ""),
                country=loc.get("country", ""),
                county=loc.get("county"),
                postcode=loc.get("postcode", ""),
                latitude=loc.get("latitude", 0.0),
                longitude=loc.get("longitude", 0.0),
            ),
            amenities=data.get("amenities", []),
            opening_times=data.get("opening_times", {}),
            fuel_types=data.get("fuel_types", []),
            temporary_closure=data.get("temporary_closure", False),
            permanent_closure=bool(data.get("permanent_closure")),
            is_motorway_service_station=data.get("is_motorway_service_station", False),
            is_supermarket_service_station=data.get(
                "is_supermarket_service_station", False
            ),
            public_phone_number=data.get("public_phone_number"),
        )


@dataclass
class FuelPrice:
    """Fuel price data."""

    fuel_type: str
    price: float
    price_last_updated: str | None = None
    price_change_effective_timestamp: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> FuelPrice:
        """Create a FuelPrice from API response data."""
        return cls(
            fuel_type=data["fuel_type"],
            price=float(data["price"]),
            price_last_updated=data.get("price_last_updated"),
            price_change_effective_timestamp=data.get(
                "price_change_effective_timestamp"
            ),
        )


@dataclass
class FuelFinderData:
    """Coordinator data container."""

    stations: dict[str, StationInfo] = field(default_factory=dict)
    prices: dict[str, list[FuelPrice]] = field(default_factory=dict)
    last_fetch_timestamp: str | None = None
