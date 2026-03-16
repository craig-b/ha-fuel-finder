"""Constants for the Fuel Finder integration."""

import logging
from datetime import timedelta

DOMAIN = "fuel_finder"
LOGGER = logging.getLogger(__package__)

BASE_URL = "https://www.fuel-finder.service.gov.uk"
TOKEN_URL = f"{BASE_URL}/api/v1/oauth/generate_access_token"
STATIONS_URL = f"{BASE_URL}/api/v1/pfs"
PRICES_URL = f"{BASE_URL}/api/v1/pfs/fuel-prices"

UPDATE_INTERVAL = timedelta(minutes=30)

FUEL_TYPES: dict[str, str] = {
    "E5": "Super Unleaded (E5)",
    "E10": "Unleaded (E10)",
    "B7_STANDARD": "Diesel (B7)",
    "B7_PREMIUM": "Premium Diesel",
    "B10": "Diesel (B10)",
    "HVO": "HVO Diesel",
}

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_STATIONS = "stations"
