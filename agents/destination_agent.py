"""
Destination Agent – orchestrates destination recommendation.

Workflow:

TripState
    ↓
PlacesService
    ↓
Raw Attractions
    ↓
Gemini
    ↓
Experience
    ↓
TripState
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from models.trip_state import TripState
from models.experience import Attraction, Experience
from services.places_service import PlacesService
from services.gemini_service import GeminiService


CATEGORY_MAP = {
    "historic": "culture",
    "castle": "culture",
    "museum": "culture",
    "monument": "culture",
    "palace": "culture",
    "temple": "culture",
    "church": "culture",
    "mosque": "culture",
    "synagogue": "culture",
    "ruins": "culture",
    "memorial": "culture",
    "archaeological": "culture",
    "library": "culture",
    "theatre": "culture",
    "opera": "culture",
    "cultural": "culture",
    "park": "nature",
    "forest": "nature",
    "lake": "nature",
    "mountain": "nature",
    "garden": "nature",
    "botanical": "nature",
    "zoo": "nature",
    "aquarium": "nature",
    "waterfall": "nature",
    "beach": "nature",
    "nature": "nature",
    "restaurant": "food",
    "cafe": "food",
    "food": "food",
    "bakery": "food",
    "market": "shopping",
    "mall": "shopping",
    "shopping": "shopping",
    "bazaar": "shopping",
    "adventure_park": "adventure",
    "trekking": "adventure",
    "adventure": "adventure",
    "sports": "adventure",
    "climbing": "adventure",
    "nightlife": "nightlife",
    "bar": "nightlife",
    "club": "nightlife",
    "pub": "nightlife",
}

VALID_CATEGORIES = {
    "culture",
    "nature",
    "food",
    "adventure",
    "shopping",
    "nightlife",
    "other",
}


def _map_category(raw_categories: list) -> str:
    """Map Geoapify categories to a single simplified category."""

    if not raw_categories:
        return "other"

    for cat in raw_categories:
        parts = cat.split(".")
        for part in parts:
            mapped = CATEGORY_MAP.get(part.lower())
            if mapped:
                return mapped

    return "other"


class DestinationAgent:
    """
    Orchestrates attraction recommendation using
    Geoapify + Gemini.
    """

    PROMPT_PATH = (
        Path(__file__).parent.parent
        / "prompts"
        / "destination.md"
    )

    def __init__(
        self,
        places_service: Optional[PlacesService] = None,
        gemini: Optional[GeminiService] = None,
    ) -> None:

        self._places = places_service or PlacesService()
        self._gemini = gemini or GeminiService()

    def run(
        self,
        state: TripState,
    ) -> TripState:
        """
        Generate destination recommendations.

        Args:
            state:
                Current TripState.

        Returns:
            Updated TripState.
        """

        if not state.destination:
            return state

        if state.trip_scope == "multi_location":
            experience = self._handle_multi_location(state)
        else:
            experience = self._handle_single_location(state)

        state.recommended_experiences = experience

        state.decision_log.append(
            f"Destination: Generated recommendations for {state.destination}."
        )

        return state

    # --------------------------------------------------------- #
    # Single Location
    # --------------------------------------------------------- #

    def _handle_single_location(
        self,
        state: TripState,
    ) -> Experience:

        place_data = self._places.get_attractions(
            state.destination
        )

        state.latitude = place_data["latitude"]
        state.longitude = place_data["longitude"]

        raw_attractions = place_data["attractions"]

        prompt = self._load_prompt()

        user_prompt = self._build_user_prompt(
            state=state,
            attractions=raw_attractions,
        )

        response = self._gemini.generate(
            prompt,
            user_prompt,
        )
        parsed = GeminiService.parse_json(response)

        experience = self._build_experience(
            parsed,
            raw_attractions,
            state.destination,
        )

        experience.cities = [state.destination]

        return experience

    # --------------------------------------------------------- #
    # Multi Location
    # --------------------------------------------------------- #

    def _handle_multi_location(
        self,
        state: TripState,
    ) -> Experience:

        """
        Handle trips spanning multiple cities.

        Step 1: Gemini selects the best cities.
        Step 2: Geoapify fetches attractions for each city.
        Step 3: Gemini curates attractions from all cities.
        """

        # ---------------------------------------------------------
        # Step 1: Ask Gemini for cities
        # ---------------------------------------------------------

        prompt = self._load_prompt()

        city_prompt = (
            f"""
Destination: {state.destination}

Duration:
{state.duration_days} days

Travel Style:
{state.travel_style}

Interests:
{state.interests}

Number of Travelers:
{state.number_of_travelers}

Return ONLY valid JSON.

Schema:

{{
    "cities": [
        "City 1",
        "City 2",
        "City 3"
    ]
}}
"""
        )

        response = self._gemini.generate(
            prompt,
            city_prompt,
        )
        parsed = GeminiService.parse_json(response)

        cities = parsed.get("cities", [])

        if not cities:
            raise RuntimeError(
                "Gemini did not return any cities."
            )

        # ---------------------------------------------------------
        # Step 2: Fetch attractions for each city
        # ---------------------------------------------------------

        all_attractions = []

        city_attractions_map = {}

        first_location = None

        for city in cities:

            place_data = self._places.get_attractions(city)

            if first_location is None:
                first_location = place_data
                state.latitude = place_data["latitude"]
                state.longitude = place_data["longitude"]

            city_attractions_map[city] = []

            for attraction in place_data["attractions"]:
                attraction["city"] = city
                all_attractions.append(attraction)
                city_attractions_map[city].append(attraction)

        # ---------------------------------------------------------
        # Step 3: Gemini curates attractions
        # ---------------------------------------------------------

        user_prompt = self._build_user_prompt(
            state=state,
            attractions=all_attractions,
            cities=cities,
        )

        response = self._gemini.generate(
            prompt,
            user_prompt,
        )
        parsed = GeminiService.parse_json(response)

        experience = self._build_experience(
            parsed,
            all_attractions,
            state.destination,
        )

        experience.cities = cities

        return experience

    # ---------------------------------------------------------
    # Build Experience
    # ---------------------------------------------------------

    def _build_experience(
        self,
        gemini_output: dict,
        raw_attractions: list,
        city: str,
    ) -> Experience:

        """
        Build an Experience model using
        Gemini's curated selection.
        """

        selected_names = set(
            gemini_output.get("selected_attractions", [])
        )

        if not selected_names:
            selected_names = {
                item["name"]
                for item in gemini_output.get("attractions", [])
            }

        attraction_models = []

        for attraction in raw_attractions:

            if attraction.get("name") not in selected_names:
                continue

            category = _map_category(
                attraction.get("categories", [])
            )

            attraction_models.append(
                Attraction(
                    name=attraction.get("name", ""),
                    category=category,
                    rating=attraction.get("rating"),
                    latitude=attraction.get("latitude", 0.0),
                    longitude=attraction.get("longitude", 0.0),
                    address=attraction.get("address"),
                    description=attraction.get("description"),
                    website=attraction.get("website"),
                    city=attraction.get("city"),
                )
            )

        return Experience(
            city=city,
            country=gemini_output.get("country", ""),
            vibe_score=gemini_output.get("vibe_score", 5),
            attractions=attraction_models,
            notes=gemini_output.get("notes"),
        )

    # ---------------------------------------------------------
    # Prompt Helpers
    # --------------------------------------------------------- #

    @staticmethod
    def _build_user_prompt(
        state: TripState,
        attractions: list,
        cities: list | None = None,
    ) -> str:
        """
        Build the prompt sent to Gemini.
        """

        compressed = [
            {
                "name": a.get("name", ""),
                "category": _map_category(
                    a.get("categories", [])
                ),
                "description": (
                    (a.get("description") or "")[:120]
                ),
                "city": a.get("city", ""),
            }
            for a in attractions
        ]

        cities_text = ""
        if cities:
            cities_text = f"\nSelected Cities:\n{json.dumps(cities, indent=2)}\n"

        return (
            f"""
Destination:
{state.destination}

Trip Scope:
{state.trip_scope}
{cities_text}
Interests:
{state.interests}

Travel Style:
{state.travel_style}

Number of Travelers:
{state.number_of_travelers}

Children Count:
{state.children_count}

Senior Citizens Count:
{state.senior_citizens_count}

Climate Assessment:
{state.climate_assessment}

Compressed Attractions:

{json.dumps(compressed, indent=2)}

Return ONLY valid JSON.
"""
        )

    @staticmethod
    def _load_prompt() -> str:
        """
        Load destination prompt.
        """

        try:
            return (
                DestinationAgent.PROMPT_PATH
                .read_text(encoding="utf-8")
            )

        except FileNotFoundError as exc:

            raise RuntimeError(
                f"Prompt not found: "
                f"{DestinationAgent.PROMPT_PATH}"
            ) from exc
