"""
LangGraph orchestration layer.

Optimized version:
- Planner runs once per user request.
- Workflow agents run sequentially.
- No recursive full-pipeline replanning.
- Event streaming is supported for Streamlit debugging.
- Each agent emits a state snapshot after completion.
- Existing destination output is reused only if it matches current destination.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Generator, Optional

from langgraph.graph import END, StateGraph

from models.trip_state import TripState
from graph.memory import TripMemory, get_checkpointer
from graph.nodes import (
    budget_node,
    climate_node,
    composer_node,
    destination_node,
    planner_node,
    transport_node,
)


MAX_REPLANS = 1

NODES = [
    "planner",
    "destination",
    "climate",
    "transport",
    "budget",
    "composer",
]

AGENT_FNS = {
    "planner": planner_node,
    "destination": destination_node,
    "climate": climate_node,
    "transport": transport_node,
    "budget": budget_node,
    "composer": composer_node,
}


def _build_context(user_message: str, history: list[dict]) -> str:
    if not history:
        return user_message

    lines = [
        f"{message.get('role', '')}: {message.get('content', '')[:200]}"
        for message in history[-10:]
    ]

    return (
        "Previous conversation:\n"
        f"{chr(10).join(lines)}\n\n"
        "Latest message:\n"
        f"{user_message}"
    )


def _normalize_text_value(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0

    return True


def _should_replan(state: TripState) -> bool:
    budget_analysis = getattr(state, "budget_analysis", None)

    if budget_analysis is None:
        return False

    feasible = getattr(budget_analysis, "feasible", True)
    replan_attempts = getattr(state, "replan_attempts", 0)

    return feasible is False and replan_attempts < MAX_REPLANS


def _normalize_workflow(workflow: list[str]) -> list[str]:
    """
    Ensures:
    - invalid node names are removed
    - planner is not repeated
    - composer appears once at the end
    """

    cleaned = []

    for node in workflow or []:
        if node not in AGENT_FNS:
            continue

        if node == "planner":
            continue

        if node == "composer":
            continue

        if node not in cleaned:
            cleaned.append(node)

    cleaned.append("composer")

    return cleaned


def _agent_output_exists(state: TripState, node: str) -> bool:
    """
    Avoid rerunning expensive agents only when the existing output
    actually belongs to the current trip request.

    Important:
    This prevents stale outputs like:
    current destination = West Bengal
    old recommended_experiences = Kerala
    """

    if node == "composer":
        return False

    if node == "destination":
        experience = getattr(state, "recommended_experiences", None)
        current_destination = getattr(state, "destination", None)

        if not experience or not current_destination:
            return False

        current_destination_text = _normalize_text_value(current_destination)

        experience_city = _normalize_text_value(
            getattr(experience, "city", "")
        )

        experience_cities = getattr(experience, "cities", []) or []

        experience_cities_normalized = [
            _normalize_text_value(city)
            for city in experience_cities
            if city
        ]

        if experience_city == current_destination_text:
            return True

        if current_destination_text in experience_cities_normalized:
            return True

        state.decision_log.append(
            "destination: Existing output does not match current destination. "
            "Destination Agent will rerun."
        )

        return False

    if node == "climate":
        climate_assessment = getattr(state, "climate_assessment", None)

        if not climate_assessment:
            return False

        return True

    if node == "transport":
        optimized_route = getattr(state, "optimized_route", None)

        if not optimized_route:
            return False

        return True

    if node == "budget":
        budget_analysis = getattr(state, "budget_analysis", None)

        if not budget_analysis:
            return False

        return True

    return False


def _safe_model_dump(value: Any) -> Any:
    if value is None:
        return None

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if isinstance(value, (str, int, float, bool, list, dict)):
        return value

    return str(value)


def _state_snapshot(state: TripState, node: str) -> dict:
    """
    Creates a compact debug snapshot after each agent.
    This is what Streamlit displays as each agent's output.
    """

    if node == "planner":
        return {
            "destination": state.destination,
            "duration_days": state.duration_days,
            "budget": state.budget,
            "travel_month": state.travel_month,
            "travel_year": state.travel_year,
            "number_of_travelers": state.number_of_travelers,
            "trip_scope": state.trip_scope,
            "workflow": state.workflow,
            "decision_log": state.decision_log[-8:],
        }

    if node == "destination":
        return {
            "destination": state.destination,
            "latitude": state.latitude,
            "longitude": state.longitude,
            "recommended_experiences": _safe_model_dump(
                state.recommended_experiences
            ),
            "decision_log": state.decision_log[-8:],
        }

    if node == "climate":
        return {
            "climate_assessment": _safe_model_dump(
                state.climate_assessment
            ),
            "decision_log": state.decision_log[-8:],
        }

    if node == "transport":
        return {
            "optimized_route": _safe_model_dump(
                state.optimized_route
            ),
            "decision_log": state.decision_log[-8:],
        }

    if node == "budget":
        return {
            "budget": state.budget,
            "budget_analysis": _safe_model_dump(
                state.budget_analysis
            ),
            "replan_attempts": state.replan_attempts,
            "decision_log": state.decision_log[-8:],
        }

    if node == "composer":
        return {
            "itinerary": state.itinerary,
            "decision_log": state.decision_log[-8:],
        }

    return {
        "decision_log": state.decision_log[-8:],
    }


def _run_agent_with_timing(state: TripState, node: str, agent_fn):
    start = time.time()
    updated_state = agent_fn(state)
    elapsed = round(time.time() - start, 2)

    return updated_state, elapsed


def _execute_workflow(state: TripState, user_message: str) -> list[str]:
    """
    Non-streaming execution.
    Runs planner once, then executes selected agents.

    Important:
    This function does NOT recursively rerun the whole workflow.
    """

    completed: list[str] = []

    state = AGENT_FNS["planner"](state, user_message)
    completed.append("planner")

    workflow = _normalize_workflow(state.workflow or [])

    for node in workflow:
        agent_fn = AGENT_FNS.get(node)

        if agent_fn is None:
            state.decision_log.append(
                f"{node}: Skipped — node function not found."
            )
            continue

        if _agent_output_exists(state, node):
            state.decision_log.append(
                f"{node}: Skipped — existing output reused."
            )
            continue

        try:
            state, elapsed = _run_agent_with_timing(state, node, agent_fn)
            state.decision_log.append(f"{node}: Completed in {elapsed}s")
            completed.append(node)

        except Exception as exc:
            state.decision_log.append(f"{node}: Skipped — {exc}")
            continue

        if node == "budget" and _should_replan(state):
            state.replan_attempts += 1
            state.decision_log.append(
                "Budget not feasible. Recursive full replanning skipped. "
                "Moving to composer."
            )

            if "composer" not in completed:
                composer_fn = AGENT_FNS.get("composer")

                if composer_fn:
                    try:
                        state, elapsed = _run_agent_with_timing(
                            state,
                            "composer",
                            composer_fn,
                        )
                        state.decision_log.append(
                            f"composer: Completed in {elapsed}s"
                        )
                        completed.append("composer")

                    except Exception as exc:
                        state.decision_log.append(
                            f"composer: Skipped — {exc}"
                        )

            break

    return completed


def _execute_workflow_events(state: TripState, user_message: str):
    """
    Streaming execution for Streamlit UI.
    Yields detailed event dictionaries.
    """

    completed: list[str] = []

    yield {
        "event": "start",
        "node": "planner",
        "message": "Planner Agent started",
    }

    start = time.time()

    try:
        state = AGENT_FNS["planner"](state, user_message)
        elapsed = round(time.time() - start, 2)
        completed.append("planner")

        state.decision_log.append(f"planner: Completed in {elapsed}s")

        yield {
            "event": "done",
            "node": "planner",
            "elapsed": elapsed,
            "message": f"Planner Agent completed in {elapsed}s",
            "workflow": state.workflow,
            "decision_log": state.decision_log[-8:],
            "snapshot": _state_snapshot(state, "planner"),
        }

    except Exception as exc:
        elapsed = round(time.time() - start, 2)

        yield {
            "event": "error",
            "node": "planner",
            "elapsed": elapsed,
            "message": f"Planner Agent failed after {elapsed}s: {exc}",
        }

        return

    workflow = _normalize_workflow(state.workflow or [])

    yield {
        "event": "info",
        "node": "workflow",
        "message": f"Normalized workflow: {workflow}",
        "workflow": workflow,
        "snapshot": {
            "workflow": workflow,
            "decision_log": state.decision_log[-8:],
        },
    }

    for node in workflow:
        agent_fn = AGENT_FNS.get(node)

        if agent_fn is None:
            yield {
                "event": "skip",
                "node": node,
                "message": f"{node} skipped because no function was found.",
            }
            continue

        if _agent_output_exists(state, node):
            state.decision_log.append(
                f"{node}: Skipped — existing output reused."
            )

            yield {
                "event": "skip",
                "node": node,
                "message": f"{node} skipped because existing output was reused.",
                "decision_log": state.decision_log[-8:],
                "snapshot": _state_snapshot(state, node),
            }

            continue

        yield {
            "event": "start",
            "node": node,
            "message": f"{node} started",
        }

        start = time.time()

        try:
            state = agent_fn(state)
            elapsed = round(time.time() - start, 2)
            completed.append(node)

            state.decision_log.append(f"{node}: Completed in {elapsed}s")

            yield {
                "event": "done",
                "node": node,
                "elapsed": elapsed,
                "message": f"{node} completed in {elapsed}s",
                "decision_log": state.decision_log[-8:],
                "snapshot": _state_snapshot(state, node),
            }

        except Exception as exc:
            elapsed = round(time.time() - start, 2)
            state.decision_log.append(f"{node}: Skipped — {exc}")

            yield {
                "event": "error",
                "node": node,
                "elapsed": elapsed,
                "message": f"{node} failed after {elapsed}s: {exc}",
                "decision_log": state.decision_log[-8:],
                "snapshot": _state_snapshot(state, node),
            }

            continue

        if node == "budget" and _should_replan(state):
            state.replan_attempts += 1
            state.decision_log.append(
                "Budget not feasible. Recursive full replanning skipped. "
                "Moving to composer."
            )

            yield {
                "event": "warning",
                "node": "budget",
                "message": (
                    "Budget not feasible. Recursive full replanning was skipped. "
                    "Moving directly to composer."
                ),
                "decision_log": state.decision_log[-8:],
                "snapshot": _state_snapshot(state, "budget"),
            }

            if "composer" not in completed:
                composer_fn = AGENT_FNS.get("composer")

                if composer_fn:
                    yield {
                        "event": "start",
                        "node": "composer",
                        "message": "composer started for budget response",
                    }

                    start = time.time()

                    try:
                        state = composer_fn(state)
                        elapsed = round(time.time() - start, 2)
                        completed.append("composer")

                        state.decision_log.append(
                            f"composer: Completed in {elapsed}s"
                        )

                        yield {
                            "event": "done",
                            "node": "composer",
                            "elapsed": elapsed,
                            "message": f"composer completed in {elapsed}s",
                            "decision_log": state.decision_log[-8:],
                            "snapshot": _state_snapshot(state, "composer"),
                        }

                    except Exception as exc:
                        elapsed = round(time.time() - start, 2)
                        state.decision_log.append(
                            f"composer: Skipped — {exc}"
                        )

                        yield {
                            "event": "error",
                            "node": "composer",
                            "elapsed": elapsed,
                            "message": f"composer failed after {elapsed}s: {exc}",
                            "decision_log": state.decision_log[-8:],
                            "snapshot": _state_snapshot(state, "composer"),
                        }

            break

    yield {
        "event": "complete",
        "node": "workflow",
        "completed": completed,
        "message": "Workflow completed",
        "decision_log": state.decision_log[-10:],
        "snapshot": {
            "completed": completed,
            "decision_log": state.decision_log[-10:],
        },
    }


class TripPlannerWorkflow:
    """
    Orchestrates the multi-agent trip planning pipeline.
    """

    def __init__(
        self,
        thread_id: str = "default",
        on_node_complete: Optional[Callable[[str, TripState], None]] = None,
    ) -> None:
        self._thread_id = thread_id
        self._on_node_complete = on_node_complete
        self._memory = TripMemory()
        self._checkpointer = get_checkpointer()
        self._app = self._build_graph().compile(checkpointer=self._checkpointer)

    def invoke(self, user_message: str) -> TripState:
        self._memory.save_message(self._thread_id, "user", user_message)

        state = self._memory.load_state(self._thread_id)

        if state is None:
            state = TripState()

        history = self._memory.load_history(self._thread_id)
        context = _build_context(user_message, history)

        result = self._app.invoke(
            {
                "trip_state": state,
                "user_message": context,
            },
            config={
                "configurable": {
                    "thread_id": self._thread_id,
                }
            },
        )

        final_state = result.get("trip_state", state)

        if not isinstance(final_state, TripState):
            final_state = state

        self._memory.save_state(self._thread_id, final_state)

        return final_state

    def stream(self, user_message: str) -> Generator[str, None, None]:
        self._memory.save_message(self._thread_id, "user", user_message)

        state = self._memory.load_state(self._thread_id)

        if state is None:
            state = TripState()

        history = self._memory.load_history(self._thread_id)
        context = _build_context(user_message, history)

        for node_name in _execute_workflow(state, context):
            self._memory.save_state(self._thread_id, state)

            yield node_name

            if self._on_node_complete:
                self._on_node_complete(node_name, state)

        self._memory.save_state(self._thread_id, state)

    def stream_events(self, user_message: str):
        self._memory.save_message(self._thread_id, "user", user_message)

        state = self._memory.load_state(self._thread_id)

        if state is None:
            state = TripState()

        history = self._memory.load_history(self._thread_id)
        context = _build_context(user_message, history)

        for event in _execute_workflow_events(state, context):
            self._memory.save_state(self._thread_id, state)

            if self._on_node_complete and event.get("event") == "done":
                node_name = event.get("node")

                if node_name:
                    self._on_node_complete(node_name, state)

            yield event

        self._memory.save_state(self._thread_id, state)

    def resume(self, user_message: str) -> TripState:
        return self.invoke(user_message)

    def get_state(self) -> Optional[TripState]:
        return self._memory.load_state(self._thread_id)

    def get_history(self) -> list[dict[str, str]]:
        return self._memory.load_history(self._thread_id)

    def reset(self) -> None:
        self._memory.delete_thread(self._thread_id)

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("executor", self._executor_node)
        graph.set_entry_point("executor")
        graph.add_edge("executor", END)
        return graph

    def _executor_node(self, state: dict) -> dict:
        trip_state = state.get("trip_state")

        if not isinstance(trip_state, TripState):
            trip_state = TripState()

        user_message = state.get("user_message", "")

        completed = _execute_workflow(trip_state, user_message)

        return {
            "trip_state": trip_state,
            "user_message": user_message,
            "completed": completed,
        }