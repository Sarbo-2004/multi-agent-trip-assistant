"""
Test script for the LangGraph integration.

Demonstrates:
1. Conversation 1: Initial trip request
2. Conversation 2: Budget update triggers replanning
3. Streaming support
4. State persistence across conversations
"""

import sys
import io

sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding="utf-8"
)

from graph.workflow import TripPlannerWorkflow
from models.trip_state import TripState


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_state_summary(state: TripState) -> None:
    """Print a concise summary of TripState."""

    print(f"  Destination: {state.destination}")
    print(f"  Trip Scope: {state.trip_scope}")
    print(f"  Travelers: {state.number_of_travelers}")
    print(f"  Duration: {state.duration_days} days")
    print(f"  Budget: {state.budget}")
    print(f"  Month/Year: {state.travel_month}/{state.travel_year}")

    if state.recommended_experiences:
        exp = state.recommended_experiences
        print(f"  Cities: {exp.cities}")
        print(
            f"  Attractions: "
            f"{[a.name for a in exp.attractions]}"
        )

    if state.budget_analysis:
        ba = state.budget_analysis
        print(f"  Total Estimated: {ba.total_estimated}")
        print(f"  Feasible: {ba.feasible}")
        if ba.recommendations:
            print(f"  Recommendations: {ba.recommendations}")

    if state.optimized_route:
        ro = state.optimized_route
        print(f"  City Order: {ro.city_order}")
        print(f"  Transport: {ro.recommended_transport}")
        print(
            f"  Total Distance: {ro.total_distance_km} km"
        )

    if state.itinerary:
        lines = state.itinerary.strip().split("\n")
        print(f"  Itinerary: {len(lines)} lines")
        for line in lines[:5]:
            print(f"    {line}")
        if len(lines) > 5:
            print(f"    ... ({len(lines) - 5} more lines)")

    print(f"  Decision Log ({len(state.decision_log)} entries):")
    for entry in state.decision_log[-3:]:
        print(f"    - {entry}")


def test_conversation_flow() -> None:
    """Test multi-turn conversation with replanning."""

    print_header("TEST: Multi-turn Conversation with Replanning")

    thread_id = "test-conversation-001"
    workflow = TripPlannerWorkflow(thread_id=thread_id)

    # ---------------------------------------------------------
    # Conversation 1: Initial request
    # ---------------------------------------------------------
    print_header("Conversation 1: Initial Request")

    msg1 = (
        "I want to visit Rajasthan for 5 days in December. "
        "4 people. We love forts, food and photography."
    )
    print(f"User: {msg1}")

    state1 = workflow.invoke(msg1)
    print("\n--- After Conversation 1 ---")
    print_state_summary(state1)

    # ---------------------------------------------------------
    # Conversation 2: Budget update (triggers replanning)
    # ---------------------------------------------------------
    print_header("Conversation 2: Budget Update")

    msg2 = "My budget is ₹25000."
    print(f"User: {msg2}")

    state2 = workflow.resume(msg2)
    print("\n--- After Conversation 2 ---")
    print_state_summary(state2)

    # ---------------------------------------------------------
    # Verify state persistence
    # ---------------------------------------------------------
    print_header("State Persistence Check")

    loaded_state = workflow.get_state()
    if loaded_state and loaded_state.destination == "Rajasthan":
        print("  State persisted correctly!")
    else:
        print("  WARNING: State not persisted correctly")

    history = workflow.get_history()
    print(f"  Conversation history: {len(history)} messages")
    for msg in history:
        print(f"    {msg['role']}: {msg['content'][:80]}...")

    # Cleanup
    workflow.reset()
    print("\n  Test complete. Thread reset.")


def test_streaming() -> None:
    """Test streaming execution."""

    print_header("TEST: Streaming Execution")

    thread_id = "test-streaming-001"
    workflow = TripPlannerWorkflow(thread_id=thread_id)

    msg = (
        "Plan a 3 day trip to Jaipur. "
        "Solo traveler. Budget ₹15000. "
        "I love forts and photography."
    )
    print(f"User: {msg}\n")

    for progress in workflow.stream(msg):
        print(f"  >> {progress}")

    final_state = workflow.get_state()
    if final_state and final_state.itinerary:
        print("\n  Final itinerary generated successfully!")
        print(
            f"  ({len(final_state.itinerary)} chars)"
        )

    # Cleanup
    workflow.reset()
    print("\n  Test complete. Thread reset.")


def test_node_progress_callback() -> None:
    """Test the node completion callback."""

    print_header("TEST: Node Progress Callback")

    thread_id = "test-callback-001"
    completed_nodes: list[str] = []

    def on_complete(node_name: str, state: TripState) -> None:
        completed_nodes.append(node_name)
        print(f"  [CALLBACK] {node_name} completed")

    workflow = TripPlannerWorkflow(
        thread_id=thread_id,
        on_node_complete=on_complete,
    )

    msg = (
        "Plan a 3 day trip to Jaipur. "
        "2 people. Budget ₹20000. "
        "We love food and culture."
    )
    print(f"User: {msg}\n")

    workflow.invoke(msg)

    print(f"\n  Nodes completed: {completed_nodes}")
    print(f"  Expected: planner, destination, climate, transport, budget, composer")

    # Cleanup
    workflow.reset()
    print("\n  Test complete. Thread reset.")


if __name__ == "__main__":
    test_conversation_flow()
    print("\n\n")
    test_streaming()
    print("\n\n")
    test_node_progress_callback()
