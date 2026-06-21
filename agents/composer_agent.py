"""
Composer Agent – generates the final travel itinerary.

Workflow:

TripState
    ↓
Gemini
    ↓
Final Itinerary
    ↓
TripState
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from models.trip_state import TripState
from services.gemini_service import GeminiService


class ComposerAgent:
    """
    Generates the final itinerary using Gemini.

    The Composer Agent performs no planning itself.
    It simply provides the fully populated TripState
    to Gemini and stores the generated itinerary.
    """

    PROMPT_PATH = (
        Path(__file__).parent.parent
        / "prompts"
        / "composer.md"
    )

    def __init__(
        self,
        gemini: Optional[GeminiService] = None,
    ) -> None:

        self._gemini = gemini or GeminiService()

    def run(
        self,
        state: TripState,
    ) -> TripState:
        """
        Generate the final itinerary.
        """

        system_prompt = self._load_prompt()

        user_prompt = self._build_user_prompt(state)

        try:
            itinerary = self._gemini.generate(
                system_prompt,
                user_prompt,
            )

        except RuntimeError as exc:
            raise RuntimeError(
                f"Failed to generate itinerary: {exc}"
            ) from exc

        state.itinerary = itinerary

        state.decision_log.append(
            "Composer: Final itinerary generated."
        )

        return state

    # ---------------------------------------------------------
    # Prompt Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        state: TripState,
    ) -> str:
        """
        Build the prompt sent to Gemini.
        """

        return f"""
Destination:
{state.destination}

Trip Scope:
{state.trip_scope}

Travel Dates:
{state.start_date} to {state.end_date}

Travel Month:
{state.travel_month}

Travel Year:
{state.travel_year}

Duration:
{state.duration_days} days

Budget:
{state.budget}

Traveler Type:
{state.traveler_type}

Number of Travelers:
{state.number_of_travelers}

Accommodation Preference:
{state.accommodation_preference}

Children Count:
{state.children_count}

Senior Citizens Count:
{state.senior_citizens_count}

Travel Style:
{state.travel_style}

Interests:
{state.interests}

Climate Assessment:
{state.climate_assessment}

Recommended Experiences:
{state.recommended_experiences}

Optimized Route:
{state.optimized_route}

Budget Analysis:
{state.budget_analysis}

Selected Cities:
{state.recommended_experiences.cities if state.recommended_experiences else []}

City Order:
{state.optimized_route.city_order if state.optimized_route else []}

City Routes:
{state.optimized_route.city_routes if state.optimized_route else []}

Generate a complete day-wise itinerary.
"""

    @staticmethod
    def _load_prompt() -> str:
        """
        Load the Composer prompt.
        """

        try:
            return ComposerAgent.PROMPT_PATH.read_text(
                encoding="utf-8"
            )

        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Prompt not found: {ComposerAgent.PROMPT_PATH}"
            ) from exc