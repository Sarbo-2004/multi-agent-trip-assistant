"""
Weather Service – wrapper around Open-Meteo APIs.

This service fetches raw forecast and historical weather data.

No weather analysis or decision making is performed here.
"""

from __future__ import annotations

from typing import Any

import requests
from requests import RequestException


class WeatherService:
    """Simple wrapper around Open-Meteo."""

    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        """
        Fetch weather forecast.

        Returns raw JSON.
        """

        try:
            response = requests.get(
                self.FORECAST_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "daily": (
                        "temperature_2m_max,"
                        "temperature_2m_min,"
                        "precipitation_sum"
                    ),
                    "timezone": "auto",
                },
                timeout=10,
            )

            response.raise_for_status()

            return response.json()

        except RequestException as e:
            raise RuntimeError(
                f"Failed to fetch forecast: {e}"
            ) from e

    def get_historical_weather(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """
        Fetch historical weather.

        Dates must be YYYY-MM-DD.
        """

        try:
            response = requests.get(
                self.HISTORICAL_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "start_date": start_date,
                    "end_date": end_date,
                    "daily": (
                        "temperature_2m_max,"
                        "temperature_2m_min,"
                        "precipitation_sum"
                    ),
                    "timezone": "auto",
                },
                timeout=10,
            )

            response.raise_for_status()

            return response.json()

        except RequestException as e:
            raise RuntimeError(
                f"Failed to fetch historical weather: {e}"
            ) from e