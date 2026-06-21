"""
Places Service – wrapper around the Geoapify APIs.

This service fetches attractions for a destination.
It performs no ranking, filtering, or recommendation logic.
"""

from __future__ import annotations

from typing import Any

import requests
from requests import RequestException

from config.settings import settings


class PlacesService:
    """Simple wrapper around the Geoapify APIs."""

    GEOCODING_URL = "https://api.geoapify.com/v1/geocode/search"
    PLACES_URL = "https://api.geoapify.com/v2/places"

    def __init__(self) -> None:
        if settings.GEOAPIFY_API_KEY is None:
            raise RuntimeError("GEOAPIFY_API_KEY is not configured.")

        self.api_key = settings.GEOAPIFY_API_KEY.get_secret_value()

    def get_attractions(self, destination: str) -> list[dict[str, Any]]:
        """
        Fetch attractions for a destination.

        Args:
            destination: Destination city or place name.

        Returns:
            List of normalized attraction dictionaries.

        Raises:
            RuntimeError: If the API request fails.
        """
        latitude, longitude = self._geocode(destination)

        try:
            response = requests.get(
                self.PLACES_URL,
                params={
                    "categories": "tourism",
                    "filter": f"circle:{longitude},{latitude},50000",
                    "limit": 50,
                    "apiKey": self.api_key,
                },
                timeout=10,
            )

            response.raise_for_status()
            data = response.json()

        except RequestException as e:
            raise RuntimeError(f"Failed to fetch attractions: {e}") from e

        attractions = []

        for feature in data.get("features", []):
            properties = feature.get("properties", {})

            attractions.append(
                {
                    "name": properties.get("name"),
                    "categories": properties.get("categories", []),
                    "latitude": properties.get("lat"),
                    "longitude": properties.get("lon"),
                    "address": properties.get("formatted"),
                    "website": properties.get("website"),
                    "description": properties.get("description"),
                }
            )

        return {
    "latitude": latitude,
    "longitude": longitude,
    "attractions": attractions,
}

    def _geocode(self, destination: str) -> tuple[float, float]:
        """
        Convert a destination name into latitude and longitude.

        Args:
            destination: Destination city or place.

        Returns:
            (latitude, longitude)

        Raises:
            RuntimeError: If the destination cannot be geocoded.
        """
        try:
            response = requests.get(
                self.GEOCODING_URL,
                params={
                    "text": destination,
                    "limit": 1,
                    "apiKey": self.api_key,
                },
                timeout=10,
            )

            response.raise_for_status()
            data = response.json()

        except RequestException as e:
            raise RuntimeError(f"Failed to geocode destination: {e}") from e

        features = data.get("features", [])

        if not features:
            raise RuntimeError(f"Destination '{destination}' not found.")

        properties = features[0]["properties"]

        return properties["lat"], properties["lon"]