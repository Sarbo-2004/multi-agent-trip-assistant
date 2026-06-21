"""
Multi-Agent Trip Planner — Streamlit App
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from graph.workflow import TripPlannerWorkflow
from models.trip_state import TripState


# ── Page config ─────────────────────────────────────────────

st.set_page_config(
    page_title="Trip Planner",
    layout="wide",
)

# ── Session state ───────────────────────────────────────────

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit-session"

if "workflow" not in st.session_state:
    st.session_state.workflow = TripPlannerWorkflow(
        thread_id=st.session_state.thread_id,
    )

if "messages" not in st.session_state:
    st.session_state.messages = []


# ── Helpers ─────────────────────────────────────────────────

def _render_result(result: TripState) -> None:
    """Render a completed trip plan."""
    parts = []
    if result.destination:
        parts.append(f"**Destination:** {result.destination}")
    if result.duration_days:
        parts.append(f"**Duration:** {result.duration_days} days")
    if result.budget:
        parts.append(f"**Budget:** {result.budget:,.0f}")

    if result.budget_analysis:
        ba = result.budget_analysis
        feasible_text = "Feasible" if ba.feasible else "Over budget"
        parts.append(
            f"**Estimated Cost:** {ba.total_estimated:,.0f} ({feasible_text})"
        )
        if ba.remaining_budget < 0:
            parts.append(f"**Shortfall:** {abs(ba.remaining_budget):,.0f}")

    if result.climate_assessment:
        ca = result.climate_assessment
        parts.append(f"**Weather:** {ca.weather_risk} risk, {ca.avg_temp_c}C avg")

    if result.optimized_route:
        ro = result.optimized_route
        parts.append(f"**Transport:** {ro.recommended_transport}")

    if parts:
        st.markdown("\n".join(parts))

    if result.itinerary:
        with st.expander("Full Itinerary", expanded=True):
            st.markdown(result.itinerary)

    if result.budget_analysis and result.budget_analysis.recommendations:
        with st.expander("Budget Recommendations"):
            for rec in result.budget_analysis.recommendations:
                st.markdown(f"- {rec}")

    if result.decision_log:
        with st.expander("Decision Log"):
            for entry in result.decision_log:
                st.markdown(f"- {entry}")


# ── Sidebar ─────────────────────────────────────────────────

with st.sidebar:
    st.title("Trip Planner")
    st.markdown("Multi-agent trip planning assistant")
    st.divider()

    thread_id = st.text_input("Session ID", value=st.session_state.thread_id)
    if thread_id != st.session_state.thread_id:
        st.session_state.thread_id = thread_id
        st.session_state.workflow = TripPlannerWorkflow(thread_id=thread_id)
        st.session_state.messages = []
        st.rerun()

    if st.button("Reset Conversation"):
        st.session_state.workflow.reset()
        st.session_state.messages = []
        st.rerun()

    st.divider()

    state = st.session_state.workflow.get_state()
    if state:
        st.markdown("### Current Trip")
        if state.destination:
            st.markdown(f"**Destination:** {state.destination}")
        if state.duration_days:
            st.markdown(f"**Duration:** {state.duration_days} days")
        if state.budget:
            st.markdown(f"**Budget:** {state.budget:,.0f}")
        if state.travel_month:
            st.markdown(
                f"**Month:** {state.travel_month}/{state.travel_year or '?'}"
            )

        st.divider()
        st.markdown("### Agent Outputs")
        ok = "OK"
        no = "--"
        st.markdown(f"{ok if state.workflow else no} Planner")
        st.markdown(f"{ok if state.recommended_experiences else no} Destination")
        st.markdown(f"{ok if state.climate_assessment else no} Climate")
        st.markdown(f"{ok if state.optimized_route else no} Transport")
        st.markdown(f"{ok if state.budget_analysis else no} Budget")
        st.markdown(f"{ok if state.itinerary else no} Composer")

        if state.replan_attempts > 0:
            st.warning(f"Replans: {state.replan_attempts}/3")

# ── Main chat area ──────────────────────────────────────────

st.title("Multi-Agent Trip Planner")
st.markdown("Describe your trip and the agents will plan it for you.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Process pending input ───────────────────────────────────

if "pending_input" not in st.session_state:
    st.session_state.pending_input = None

if st.session_state.pending_input is not None:
    user_input = st.session_state.pending_input
    st.session_state.pending_input = None

    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Run the workflow synchronously with a status indicator
    with st.chat_message("assistant"):
        with st.status("Planning your trip...", expanded=True) as status:
            wf = st.session_state.workflow
            step_container = st.empty()

            completed_nodes: list[str] = []
            for node in wf.stream(user_input):
                completed_nodes.append(node)
                step_container.text(f"✓ {node} complete")

            result = wf.get_state()
            status.update(label="Trip planned!", state="complete")

        if result is not None:
            _render_result(result)
        else:
            st.error("No result was produced.")

# ── Chat input ──────────────────────────────────────────────

user_input = st.chat_input(
    "Describe your trip (e.g., 'Plan a 5 day trip to Jaipur in December, "
    "budget 25000 rupees')"
)
if user_input:
    st.session_state.pending_input = user_input
    st.rerun()
