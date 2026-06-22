"""
Places Service – wrapper around the Geoapify APIs.

This service fetches attractions for a destination.
It performs no ranking, filtering, or recommendation logic.
It handles SSL/network failures gracefully.
"""

from __future__ import annotations

from typing import Any

import certifi
import requests
import urllib3
from requests import RequestException

from config.settings import settings


class PlacesService:
    """Simple wrapper around the Geoapify APIs."""

    GEOCODING_URL = "https://api.geoapify.com/v1/geocode/search"
    PLACES_URL = "https://api.geoapify.com/v2/places"

    def __init__(self) -> None:
        self.api_key = None

        if settings.GEOAPIFY_API_KEY is not None:
            self.api_key = settings.GEOAPIFY_API_KEY.get_secret_value()

        self.verify_ssl = settings.GEOAPIFY_VERIFY_SSL

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _verify_value(self):
        return certifi.where() if self.verify_ssl else False

    def get_attractions(self, destination: str) -> dict[str, Any]:
        """
        Fetch attractions for a destination.

        Returns:
            Dictionary with success flag, coordinates, attractions, and fallback information.
        """

        if not self.api_key:
            return {
                "success": False,
                "destination": destination,
                "latitude": None,
                "longitude": None,
                "attractions": [],
                "error": "geoapify_api_key_missing",
                "message": "GEOAPIFY_API_KEY is not configured.",
                "fallback": True,
            }

        geocode_result = self._geocode(destination)

        if not geocode_result.get("success"):
            return {
                "success": False,
                "destination": destination,
                "latitude": None,
                "longitude": None,
                "attractions": [],
                "error": geocode_result.get("error"),
                "message": geocode_result.get("message"),
                "fallback": True,
            }

        latitude = geocode_result.get("latitude")
        longitude = geocode_result.get("longitude")

        try:
            response = requests.get(
                self.PLACES_URL,
                params={
                    "categories": "tourism",
                    "filter": f"circle:{longitude},{latitude},50000",
                    "limit": 50,
                    "apiKey": self.api_key,
                },
                timeout=15,
                verify=self._verify_value(),
            )

            response.raise_for_status()
            data = response.json()

        except requests.exceptions.SSLError as exc:
            return {
                "success": False,
                "destination": destination,
                "latitude": latitude,
                "longitude": longitude,
                "attractions": [],
                "error": "ssl_error",
                "message": str(exc),
                "fallback": True,
            }

        except RequestException as exc:
            return {
                "success": False,
                "destination": destination,
                "latitude": latitude,
                "longitude": longitude,
                "attractions": [],
                "error": "places_request_failed",
                "message": str(exc),
                "fallback": True,
            }

        attractions = []

        for feature in data.get("features", []):
            properties = feature.get("properties", {})
            name = properties.get("name")

            if not name:
                continue

            attractions.append(
                {
                    "name": name,
                    "categories": properties.get("categories", []),
                    "latitude": properties.get("lat"),
                    "longitude": properties.get("lon"),
                    "address": properties.get("formatted"),
                    "website": properties.get("website"),
                    "description": properties.get("description"),
                    "city": properties.get("city"),
                    "state": properties.get("state"),
                    "country": properties.get("country"),
                }
            )

        return {
            "success": True,
            "destination": destination,
            "latitude": latitude,
            "longitude": longitude,
            "formatted": geocode_result.get("formatted"),
            "city": geocode_result.get("city"),
            "state": geocode_result.get("state"),
            "country": geocode_result.get("country"),
            "attractions": attractions,
        }

    def _geocode(self, destination: str) -> dict[str, Any]:
        """
        Convert a destination name into latitude and longitude.

        Returns:
            Dictionary with success flag, coordinates, and error details.
        """

        if not destination:
            return {
                "success": False,
                "error": "destination_missing",
                "message": "Destination is missing.",
            }

        if not self.api_key:
            return {
                "success": False,
                "error": "geoapify_api_key_missing",
                "message": "GEOAPIFY_API_KEY is not configured.",
            }

        try:
            response = requests.get(
                self.GEOCODING_URL,
                params={
                    "text": destination,
                    "limit": 1,
                    "apiKey": self.api_key,
                },
                timeout=15,
                verify=self._verify_value(),
            )

            response.raise_for_status()
            data = response.json()

        except requests.exceptions.SSLError as exc:
            return {
                "success": False,
                "error": "ssl_error",
                "message": str(exc),
            }

        except RequestException as exc:
            return {
                "success": False,
                "error": "geocode_request_failed",
                "message": str(exc),
            }

        features = data.get("features", [])

        if not features:
            return {
                "success": False,
                "error": "destination_not_found",
                "message": f"Destination '{destination}' not found.",
            }

        properties = features[0].get("properties", {})

        latitude = properties.get("lat")
        longitude = properties.get("lon")

        if latitude is None or longitude is None:
            return {
                "success": False,
                "error": "coordinates_missing",
                "message": f"Coordinates not found for destination '{destination}'.",
            }

        return {
            "success": True,
            "latitude": latitude,
            "longitude": longitude,
            "formatted": properties.get("formatted", destination),
            "city": properties.get("city"),
            "state": properties.get("state"),
            "country": properties.get("country"),
        }