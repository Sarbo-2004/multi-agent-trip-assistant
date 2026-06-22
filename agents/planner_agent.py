"""
Planner Agent – extracts structured travel constraints from natural language.

This agent is responsible ONLY for:
- Loading the planner prompt
- Calling GeminiService.generate()
- Parsing the JSON response
- Populating TripState with extracted values
- Appending decision_log entries

All other planning tasks (weather, destinations, routes, budgets) are
delegated to specialized agents.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from services.gemini_service import GeminiService
from models.trip_state import TripState


class PlannerAgent:
    """Extracts travel constraints and populates TripState."""

    PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "planner.md"

    def __init__(self, gemini: Optional[GeminiService] = None) -> None:
        self._gemini = gemini or GeminiService()

    def run(self, user_message: str, state: Optional[TripState] = None) -> TripState:
        """
        Extract constraints from *user_message* and update *state*.

        Args:
            user_message: Natural language travel request.
            state: Existing TripState to update; creates new one if None.

        Returns:
            Updated TripState with extracted constraints and decision log entry.

        Raises:
            RuntimeError: If Gemini returns invalid JSON or the prompt file cannot be read.
        """
        state = state or TripState()

        # Load the prompt from file
        prompt_text = self._load_prompt()

        # Call Gemini to extract constraints
        raw_response = self._gemini.generate(
            system_prompt=prompt_text,
            user_prompt=user_message,
        )

        # Parse the JSON response
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gemini returned invalid JSON: {exc}") from exc

        # Populate the state
        new_destination = data.get("destination")

        if new_destination and new_destination != state.destination:
            state.destination = new_destination

            state.recommended_experiences = None
            state.climate_assessment = None
            state.optimized_route = None
            state.budget_analysis = None
            state.itinerary = None

            state.latitude = None
            state.longitude = None

            state.decision_log.append(
                f"Planner: Destination changed to {new_destination}. Cleared old agent outputs."
        )

        else:
            state.destination = new_destination or state.destination
        state.start_date = self._parse_date(data.get("start_date"))
        if state.start_date:
            state.travel_month = state.travel_month or state.start_date.month
            state.travel_year = state.travel_year or state.start_date.year
        state.end_date = self._parse_date(data.get("end_date"))
        state.travel_month = data.get("travel_month")
        state.travel_year = data.get("travel_year")

        if state.travel_month and not state.travel_year:
            current_year = datetime.now().year
            current_month = datetime.now().month
            if state.travel_month >= current_month:
                state.travel_year = current_year
            else:
                state.travel_year = current_year + 1
        state.duration_days = data.get("duration_days")
        state.budget = data.get("budget")
        state.traveler_type = data.get("traveler_type")
        state.number_of_travelers = data.get("number_of_travelers")
        state.accommodation_preference = data.get("accommodation_preference")
        state.children_count = data.get("children_count")
        state.senior_citizens_count = data.get("senior_citizens_count")
        state.travel_style = data.get("travel_style")
        state.interests = data.get("interests") or []
        state.trip_scope = data.get("trip_scope", "single_location")

        # Decide workflow based on user intent
        state.workflow = self._decide_workflow(user_message, state)

        # Append decision log
        state.decision_log.append(
            f"Planner: Extracted travel constraints for destination "
            f"'{state.destination}'. "
            f"Workflow: {' -> '.join(state.workflow)}"
        )

        return state

    # All valid node names that can appear in a workflow
    _ALL_NODES: List[str] = [
        "destination",
        "climate",
        "transport",
        "budget",
        "composer",
    ]

    @staticmethod
    def _decide_workflow(user_message: str, state: TripState) -> List[str]:
        """
        Decide which nodes to execute based on user intent.

        Uses simple keyword rules — no LLM involved.
        Always includes 'composer' as the final node.

        Rules (evaluated in order, first match wins):
            1. Weather-only queries       → climate → composer
            2. Itinerary optimization      → transport → composer
            3. Budget-focused planning     → destination → budget → transport → climate → composer
            4. Default / full planning     → destination → climate → transport → budget → composer
        """

        msg = user_message.lower()

        # --- Rule 1: weather / climate-only queries ---
        weather_keywords = [
            "weather", "climate", "temperature", "rain", "monsoon",
            "good time", "best time", "good season", "good month",
            "season", "forecast",
        ]
        for kw in weather_keywords:
            if kw in msg:
                return ["climate", "composer"]

        # --- Rule 2: itinerary / route optimization ---
        optimize_keywords = [
            "optimize", "optimise", "reorder", "rearrange",
            "shortest route", "best route", "efficient itinerary",
            "improve my itinerary", "change the order",
        ]
        for kw in optimize_keywords:
            if kw in msg:
                return ["transport", "composer"]

        # --- Rule 3: budget-focused planning ---
        budget_keywords = [
            "cheapest", "lowest cost", "budget-friendly",
            "affordable", "economical", "cheap",
            "low budget", "tight budget",
        ]
        for kw in budget_keywords:
            if kw in msg:
                return ["destination", "budget", "transport", "climate", "composer"]

        # --- Rule 4: default full planning ---
        return ["destination", "climate", "transport", "budget", "composer"]

    @staticmethod
    def _load_prompt() -> str:
        """Load the planner prompt from the prompts directory."""
        try:
            return PlannerAgent.PROMPT_PATH.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise RuntimeError(f"Prompt file not found: {PlannerAgent.PROMPT_PATH}") from exc

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[date]:
        """Parse ISO date string to date object, returning None if empty."""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None