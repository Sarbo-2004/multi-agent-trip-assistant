"""
LangGraph node wrappers.

Each node is a thin wrapper that:
1. Calls the corresponding agent's run() method
2. Returns the updated TripState

No business logic lives here.
"""

from __future__ import annotations

from models.trip_state import TripState
from agents.planner_agent import PlannerAgent
from agents.destination_agent import DestinationAgent
from agents.climate_agent import ClimateAgent
from agents.transport_agent import TransportAgent
from agents.budget_agent import BudgetAgent
from agents.composer_agent import ComposerAgent


def planner_node(state: TripState, user_message: str = "") -> TripState:
    return PlannerAgent().run(user_message, state)


def destination_node(state: TripState) -> TripState:
    return DestinationAgent().run(state)


def climate_node(state: TripState) -> TripState:
    return ClimateAgent().run(state)


def transport_node(state: TripState) -> TripState:
    return TransportAgent().run(state)


def budget_node(state: TripState) -> TripState:
    return BudgetAgent().run(state)


def composer_node(state: TripState) -> TripState:
    return ComposerAgent().run(state)
