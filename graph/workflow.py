"""
LangGraph orchestration layer.

Architecture
============

Single LangGraph node that executes the entire workflow loop.

The PlannerAgent sets state.workflow (an ordered list of agent names).
The executor node walks that list, running each agent in sequence.
After budget, if feasible == False, it routes back to planner for
replanning (max 3 attempts via state.replan_attempts).
"""

from __future__ import annotations

from typing import Callable, Generator, Optional

from langgraph.graph import END, StateGraph

from models.trip_state import TripState
from graph.memory import TripMemory, get_checkpointer
from agents.planner_agent import PlannerAgent
from graph.nodes import (
    budget_node,
    climate_node,
    composer_node,
    destination_node,
    planner_node,
    transport_node,
)

# ── Constants ──────────────────────────────────────────────

MAX_REPLANS = 3

NODES = ["planner", "destination", "climate", "transport", "budget", "composer"]

AGENT_FNS = {
    "planner": planner_node,
    "destination": destination_node,
    "climate": climate_node,
    "transport": transport_node,
    "budget": budget_node,
    "composer": composer_node,
}


# ── Helpers ────────────────────────────────────────────────

def _build_context(user_message: str, history: list[dict]) -> str:
    if not history:
        return user_message
    lines = [f"{m['role']}: {m['content'][:200]}" for m in history[-10:]]
    return f"Previous conversation:\n{chr(10).join(lines)}\n\nLatest message:\n{user_message}"


def _should_replan(state: TripState) -> bool:
    ba = state.budget_analysis
    return ba is not None and not ba.feasible and state.replan_attempts < MAX_REPLANS


def _execute_workflow(state: TripState, user_message: str) -> list[str]:
    """
    Always run planner first to set state.workflow,
    then execute each remaining agent in order.
    Returns the list of node names that completed.
    """
    completed: list[str] = []

    # Planner always runs first — it sets state.workflow
    state = AGENT_FNS["planner"](state, user_message)
    completed.append("planner")

    workflow = state.workflow or []
    for node in workflow:
        if node == "planner":
            continue

        agent_fn = AGENT_FNS.get(node)
        if agent_fn is None:
            continue

        try:
            state = agent_fn(state)
        except Exception as exc:
            state.decision_log.append(f"{node}: Skipped — {exc}")
            continue

        completed.append(node)

        if node == "budget" and _should_replan(state):
            state.replan_attempts += 1
            state.workflow = PlannerAgent._decide_workflow(user_message, state)
            return completed + _execute_workflow(state, user_message)

    return completed


# ── Public interface ───────────────────────────────────────

class TripPlannerWorkflow:
    """
    Orchestrates the multi-agent trip planning pipeline.

    Usage::

        w = TripPlannerWorkflow(thread_id="user-123")
        state = w.invoke("Plan a 5 day trip to Jaipur...")
        for step in w.stream("Plan a trip..."):
            print(step)
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

    # ── Public API ──────────────────────────────────────────

    def invoke(self, user_message: str) -> TripState:
        """Run the full pipeline and return the final TripState."""
        self._memory.save_message(self._thread_id, "user", user_message)

        state = self._memory.load_state(self._thread_id)
        if state is None:
            state = TripState()

        history = self._memory.load_history(self._thread_id)
        context = _build_context(user_message, history)

        result = self._app.invoke(
            {"trip_state": state, "user_message": context},
            config={"configurable": {"thread_id": self._thread_id}},
        )

        final_state = result.get("trip_state", state)
        if not isinstance(final_state, TripState):
            final_state = state
        self._memory.save_state(self._thread_id, final_state)
        return final_state

    def stream(self, user_message: str) -> Generator[str, None, None]:
        """
        Run the pipeline with streaming progress.
        Yields node names as they complete.
        """
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

    def resume(self, user_message: str) -> TripState:
        """Resume from a previous conversation."""
        return self.invoke(user_message)

    def get_state(self) -> Optional[TripState]:
        return self._memory.load_state(self._thread_id)

    def get_history(self) -> list[dict[str, str]]:
        return self._memory.load_history(self._thread_id)

    def reset(self) -> None:
        self._memory.delete_thread(self._thread_id)

    # ── Graph construction ──────────────────────────────────

    def _build_graph(self) -> StateGraph:
        g = StateGraph(dict)
        g.add_node("executor", self._executor_node)
        g.set_entry_point("executor")
        g.add_edge("executor", END)
        return g

    def _executor_node(self, state: dict) -> dict:
        ts = state.get("trip_state")
        if not isinstance(ts, TripState):
            ts = TripState()
        user_message = state.get("user_message", "")

        completed = _execute_workflow(ts, user_message)

        return {"trip_state": ts, "user_message": user_message, "completed": completed}
