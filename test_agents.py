import sys
import io
from pprint import pprint

from agents.planner_agent import PlannerAgent
from agents.destination_agent import DestinationAgent
from agents.climate_agent import ClimateAgent
from agents.transport_agent import TransportAgent
from agents.budget_agent import BudgetAgent
from agents.composer_agent import ComposerAgent

from models.trip_state import TripState


sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding="utf-8"
)


def main():

    user_query = (
        "Plan a 5 day trip to Rajasthan in December with a budget of ₹30000. "
        "4 people. "
        "We prefer a hotel stay. "
        "We love forts, food and photography."
    )

    print("=" * 80)
    print("PLANNER")
    print("=" * 80)

    planner = PlannerAgent()

    state = planner.run(user_query)

    pprint(state.model_dump())

    print("=" * 80)
    print("DESTINATION")
    print("=" * 80)

    destination = DestinationAgent()

    state = destination.run(state)

    pprint(state.recommended_experiences)

    print("=" * 80)
    print("CLIMATE")
    print("=" * 80)

    climate = ClimateAgent()

    state = climate.run(state)

    pprint(state.climate_assessment)

    print("=" * 80)
    print("TRANSPORT")
    print("=" * 80)

    transport = TransportAgent()

    state = transport.run(state)

    pprint(state.optimized_route)

    print("=" * 80)
    print("BUDGET")
    print("=" * 80)

    budget = BudgetAgent()

    state = budget.run(state)

    pprint(state.budget_analysis)

    print("=" * 80)
    print("COMPOSER")
    print("=" * 80)

    composer = ComposerAgent()

    state = composer.run(state)

    print(state.itinerary)

    print("=" * 80)
    print("DECISION LOG")
    print("=" * 80)

    pprint(state.decision_log)


if __name__ == "__main__":
    main()
