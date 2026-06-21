"""
Routing Service – wrapper around the OpenRouteService Directions API.

This service fetches route information between locations.
It performs no optimization or itinerary planning.
"""

from __future__ import annotations

import math
from typing import Any

import requests
from requests import RequestException

from config.settings import settings


class RoutingService:
    """Simple wrapper around the OpenRouteService Directions API."""

    BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

    def __init__(self) -> None:
        if settings.OPENROUTESERVICE_API_KEY is None:
            raise RuntimeError("OPENROUTESERVICE_API_KEY is not configured.")

        self.api_key = settings.OPENROUTESERVICE_API_KEY.get_secret_value()

    def optimize_route(
        self,
        coordinates: list[list[float]],
    ) -> dict[str, Any]:
        """
        Fetch an optimized route.

        Args:
            coordinates:
                List of [longitude, latitude] pairs.

        Returns:
            Simplified route information.
        """

        if len(coordinates) < 2:
            raise ValueError(
                "At least two coordinates are required."
            )

        # Try full route first
        result = self._try_route(coordinates)
        if result is not None:
            return result

        # Fallback: try consecutive pairs and sum
        result = self._fallback_route(coordinates)
        if result is not None:
            return result

        # Last resort: haversine estimate
        return self._estimate_route(coordinates)

    def _try_route(
        self,
        coordinates: list[list[float]],
    ) -> dict[str, Any] | None:
        """Attempt to get a route for given coordinates."""

        try:
            response = requests.post(
                self.BASE_URL,
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "coordinates": coordinates,
                },
                timeout=15,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            summary = data["routes"][0]["summary"]

            distance_km = round(
                summary["distance"] / 1000,
                2,
            )
            duration_minutes = round(
                summary["duration"] / 60
            )

            return {
                "total_distance_km": distance_km,
                "total_duration_minutes": duration_minutes,
                "recommended_transport": _suggest_transport(
                    distance_km
                ),
                "optimized_order": list(
                    range(len(coordinates))
                ),
                "geometry": data["routes"][0].get(
                    "geometry"
                ),
            }

        except (RequestException, KeyError, IndexError):
            return None

    def _fallback_route(
        self,
        coordinates: list[list[float]],
    ) -> dict[str, Any] | None:
        """
        Fallback: sum distances of consecutive pairs,
        skipping unroutable segments.
        """

        total_distance = 0.0
        total_duration = 0.0
        valid_segments = 0

        for i in range(len(coordinates) - 1):
            pair = [coordinates[i], coordinates[i + 1]]
            result = self._try_route(pair)
            if result is not None:
                total_distance += result["total_distance_km"]
                total_duration += result["total_duration_minutes"]
                valid_segments += 1

        if valid_segments == 0:
            return None

        return {
            "total_distance_km": round(total_distance, 2),
            "total_duration_minutes": round(total_duration),
            "recommended_transport": _suggest_transport(
                total_distance
            ),
            "optimized_order": list(range(len(coordinates))),
            "geometry": None,
        }

    @staticmethod
    def _estimate_route(
        coordinates: list[list[float]],
    ) -> dict[str, Any]:
        """Rough estimate using haversine distance."""

        total_km = 0.0

        for i in range(len(coordinates) - 1):
            lon1, lat1 = coordinates[i]
            lon2, lat2 = coordinates[i + 1]

            R = 6371
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(lat1))
                * math.cos(math.radians(lat2))
                * math.sin(dlon / 2) ** 2
            )
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            total_km += R * c

        total_km *= 1.3
        duration_min = (total_km / 30) * 60

        return {
            "total_distance_km": round(total_km, 2),
            "total_duration_minutes": round(duration_min),
            "recommended_transport": "car"
            if total_km > 15
            else "bike"
            if total_km > 2
            else "walking",
            "optimized_order": list(range(len(coordinates))),
            "geometry": None,
        }


def _suggest_transport(distance_km: float) -> str:
    if distance_km <= 2:
        return "walking"
    elif distance_km <= 15:
        return "bike"
    else:
        return "car"
