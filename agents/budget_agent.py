"""
Budget Agent – estimates trip expenses using Gemini.

Workflow:

TripState
    ↓
Gemini
    ↓
BudgetAnalysis
    ↓
TripState
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from models.trip_state import TripState
from models.budget_analysis import (
    BudgetAnalysis,
    CostBreakdown,
)
from services.gemini_service import GeminiService


class BudgetAgent:
    """Estimate trip expenses using Gemini."""

    PROMPT_PATH = (
        Path(__file__).parent.parent
        / "prompts"
        / "budget.md"
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

        if state.budget is None:
            raise RuntimeError(
                "User budget is required."
            )

        system_prompt = self._load_prompt()

        user_prompt = self._build_user_prompt(
            state
        )

        try:

            response = self._gemini.generate(
                system_prompt,
                user_prompt,
            )

            analysis = GeminiService.parse_json(response)

        except Exception as exc:

            raise RuntimeError(
                f"Budget analysis failed: {exc}"
            ) from exc

        breakdown = CostBreakdown(
            accommodation=analysis["breakdown"]["accommodation"],
            transport=analysis["breakdown"]["transport"],
            food=analysis["breakdown"]["food"],
            activities=analysis["breakdown"]["activities"],
            miscellaneous=analysis["breakdown"]["miscellaneous"],
        )

        recommendations = analysis.get("recommendations", [])

        state.budget_analysis = BudgetAnalysis(
            total_estimated=analysis["total_estimated"],
            remaining_budget=analysis["remaining_budget"],
            feasible=analysis["feasible"],
            breakdown=breakdown,
            recommendations=recommendations,
            notes=analysis.get("notes"),
        )

        state.decision_log.append(
            "Budget: Cost analysis completed."
        )

        return state

    # ---------------------------------------------------------
    # Prompt Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        state: TripState,
    ) -> str:

        return f"""
Destination:
{state.destination}

Trip Scope:
{state.trip_scope}

Duration:
{state.duration_days}

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

Estimate the complete trip cost.

Return ONLY valid JSON.
"""

    @staticmethod
    def _load_prompt() -> str:

        try:

            return BudgetAgent.PROMPT_PATH.read_text(
                encoding="utf-8"
            )

        except FileNotFoundError as exc:

            raise RuntimeError(
                f"Prompt not found: {BudgetAgent.PROMPT_PATH}"
            ) from exc