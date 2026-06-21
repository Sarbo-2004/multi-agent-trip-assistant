"""
Climate Agent – orchestrates weather analysis using
WeatherService + Gemini.

Workflow:

TripState
    ↓
WeatherService (per city)
    ↓
Raw Weather
    ↓
Gemini
    ↓
ClimateAssessment
    ↓
TripState
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from models.trip_state import TripState
from models.climate_assessment import ClimateAssessment
from services.weather_service import WeatherService
from services.gemini_service import GeminiService


class ClimateAgent:
    """
    Generates a climate assessment for the trip.

    For multi-location trips, fetches weather for every
    selected city and produces one overall assessment.
    """

    PROMPT_PATH = (
        Path(__file__).parent.parent
        / "prompts"
        / "climate.md"
    )

    def __init__(
        self,
        weather_service: Optional[WeatherService] = None,
        gemini: Optional[GeminiService] = None,
    ) -> None:

        self._weather = weather_service or WeatherService()
        self._gemini = gemini or GeminiService()

    def run(
        self,
        state: TripState,
    ) -> TripState:
        """
        Generate a climate assessment.
        """

        if not state.destination:
            return state

        experience = state.recommended_experiences
        if experience is None:
            return state

        cities = experience.cities or [state.destination]

        if len(cities) > 1:
            weather_data = self._fetch_multi_city_weather(
                cities, state
            )
        else:
            weather_data = self._fetch_single_city_weather(
                cities[0], state
            )

        if not weather_data:
            return state

        prompt = self._load_prompt()

        user_prompt = self._build_user_prompt(
            state,
            weather_data,
        )

        response = self._gemini.generate(
            prompt,
            user_prompt,
        )

        try:
            analysis = GeminiService.parse_json(response)
        except ValueError as exc:
            raise RuntimeError(
                "Gemini returned invalid JSON."
            ) from exc

        state.climate_assessment = ClimateAssessment(
            weather_risk=analysis["weather_risk"],
            avg_temp_c=analysis["avg_temp_c"],
            precipitation_mm=analysis["precipitation_mm"],
            weather_summary=analysis.get("weather_summary"),
        )

        state.decision_log.append(
            f"Climate: Weather analyzed for {state.destination}."
        )

        return state

    # ---------------------------------------------------------
    # Single City Weather
    # ---------------------------------------------------------

    def _fetch_single_city_weather(
        self,
        city: str,
        state: TripState,
    ) -> dict | None:
        """Fetch weather for a single city."""

        from services.places_service import PlacesService

        places = PlacesService()

        try:
            place_data = places.get_attractions(city)
            lat = place_data["latitude"]
            lon = place_data["longitude"]
        except Exception:
            return None

        return self._get_weather_for_coords(lat, lon, state)

    # ---------------------------------------------------------
    # Multi City Weather
    # ---------------------------------------------------------

    def _fetch_multi_city_weather(
        self,
        cities: list[str],
        state: TripState,
    ) -> dict | None:
        """Fetch weather for multiple cities."""

        from services.places_service import PlacesService

        places = PlacesService()

        city_weather = {}

        for city in cities:
            try:
                place_data = places.get_attractions(city)
                lat = place_data["latitude"]
                lon = place_data["longitude"]
                weather = self._get_weather_for_coords(
                    lat, lon, state
                )
                if weather:
                    city_weather[city] = weather
            except Exception:
                continue

        if not city_weather:
            return None

        return {"cities": city_weather}

    # ---------------------------------------------------------
    # Weather Fetch
    # ---------------------------------------------------------

    @staticmethod
    def _get_weather_for_coords(
        latitude: float,
        longitude: float,
        state: TripState,
    ) -> dict | None:
        """Fetch weather data based on available trip information."""

        if latitude is None or longitude is None:
            return None

        weather = WeatherService()

        if state.start_date and state.end_date:
            return weather.get_forecast(
                latitude=latitude,
                longitude=longitude,
            )

        if state.travel_month and state.travel_year:
            start = (
                f"{state.travel_year}-"
                f"{state.travel_month:02d}-01"
            )
            end = (
                f"{state.travel_year}-"
                f"{state.travel_month:02d}-28"
            )
            return weather.get_historical_weather(
                latitude=latitude,
                longitude=longitude,
                start_date=start,
                end_date=end,
            )

        return weather.get_forecast(
            latitude=latitude,
            longitude=longitude,
        )

    # ---------------------------------------------------------
    # Prompt Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        state: TripState,
        weather_data: dict,
    ) -> str:
        """
        Build the user prompt sent to Gemini.
        """

        if state.start_date and state.end_date:
            travel_period = (
                f"{state.start_date.isoformat()} "
                f"to {state.end_date.isoformat()}"
            )
        elif state.travel_month and state.travel_year:
            travel_period = (
                f"{state.travel_month:02d}/{state.travel_year}"
            )
        else:
            travel_period = "Unknown"

        return f"""
Destination:
{state.destination}

Trip Scope:
{state.trip_scope}

Travel Period:
{travel_period}

Travel Style:
{state.travel_style}

Traveler Type:
{state.traveler_type}

Raw Weather Data:

{json.dumps(weather_data, indent=2)}

Return ONLY valid JSON following the schema defined in the system prompt.
"""

    @staticmethod
    def _load_prompt() -> str:
        """
        Load the Climate Agent prompt.
        """

        try:
            return ClimateAgent.PROMPT_PATH.read_text(
                encoding="utf-8"
            )

        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Prompt not found: {ClimateAgent.PROMPT_PATH}"
            ) from exc
