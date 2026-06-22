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


st.set_page_config(
    page_title="Trip Planner",
    layout="wide",
)


if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit-session"

if "workflow" not in st.session_state:
    st.session_state.workflow = TripPlannerWorkflow(
        thread_id=st.session_state.thread_id,
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_input" not in st.session_state:
    st.session_state.pending_input = None


def _render_result(result: TripState) -> None:
    parts = []

    if result.destination:
        parts.append(f"**Destination:** {result.destination}")

    if result.duration_days:
        parts.append(f"**Duration:** {result.duration_days} days")

    if result.budget:
        parts.append(f"**Budget:** ₹{result.budget:,.0f}")

    if result.budget_analysis:
        budget_analysis = result.budget_analysis
        feasible_text = "Feasible" if budget_analysis.feasible else "Over budget"

        parts.append(
            f"**Estimated Cost:** ₹{budget_analysis.total_estimated:,.0f} ({feasible_text})"
        )

        if budget_analysis.remaining_budget < 0:
            parts.append(
                f"**Shortfall:** ₹{abs(budget_analysis.remaining_budget):,.0f}"
            )

    if result.climate_assessment:
        climate_assessment = result.climate_assessment
        parts.append(
            f"**Weather:** {climate_assessment.weather_risk} risk, "
            f"{climate_assessment.avg_temp_c}°C avg"
        )

    if result.optimized_route:
        optimized_route = result.optimized_route
        parts.append(f"**Transport:** {optimized_route.recommended_transport}")

    if parts:
        st.markdown("\n\n".join(parts))

    if result.itinerary:
        with st.expander("Full Itinerary", expanded=True):
            st.markdown(result.itinerary)

    if result.budget_analysis and result.budget_analysis.recommendations:
        with st.expander("Budget Recommendations", expanded=False):
            for recommendation in result.budget_analysis.recommendations:
                st.markdown(f"- {recommendation}")

    if result.decision_log:
        with st.expander("Decision Log", expanded=False):
            for entry in result.decision_log:
                st.markdown(f"- {entry}")


def _event_icon(event_type: str) -> str:
    icons = {
        "start": "🔄",
        "done": "✅",
        "skip": "⏭️",
        "warning": "⚠️",
        "error": "❌",
        "complete": "🏁",
        "info": "ℹ️",
    }

    return icons.get(event_type, "ℹ️")


def _build_assistant_message(result: TripState) -> str:
    assistant_message_parts = []

    if result.destination:
        assistant_message_parts.append(f"Destination: {result.destination}")

    if result.duration_days:
        assistant_message_parts.append(f"Duration: {result.duration_days} days")

    if result.budget:
        assistant_message_parts.append(f"Budget: ₹{result.budget:,.0f}")

    if result.itinerary:
        assistant_message_parts.append(result.itinerary)

    assistant_content = "\n\n".join(assistant_message_parts).strip()

    if not assistant_content:
        assistant_content = (
            "Trip planning completed. Please check the generated output above."
        )

    return assistant_content


with st.sidebar:
    st.title("Trip Planner")
    st.markdown("Multi-agent trip planning assistant")
    st.divider()

    thread_id = st.text_input("Session ID", value=st.session_state.thread_id)

    if thread_id != st.session_state.thread_id:
        st.session_state.thread_id = thread_id
        st.session_state.workflow = TripPlannerWorkflow(thread_id=thread_id)
        st.session_state.messages = []
        st.session_state.pending_input = None
        st.rerun()

    if st.button("Reset Conversation"):
        st.session_state.workflow.reset()
        st.session_state.messages = []
        st.session_state.pending_input = None

        st.session_state.workflow = TripPlannerWorkflow(
            thread_id=st.session_state.thread_id,
        )

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
            st.markdown(f"**Budget:** ₹{state.budget:,.0f}")

        if state.travel_month:
            st.markdown(
                f"**Month:** {state.travel_month}/{state.travel_year or '?'}"
            )

        st.divider()

        st.markdown("### Agent Outputs")

        ok = "✅"
        no = "—"

        st.markdown(f"{ok if state.workflow else no} Planner")
        st.markdown(f"{ok if state.recommended_experiences else no} Destination")
        st.markdown(f"{ok if state.climate_assessment else no} Climate")
        st.markdown(f"{ok if state.optimized_route else no} Transport")
        st.markdown(f"{ok if state.budget_analysis else no} Budget")
        st.markdown(f"{ok if state.itinerary else no} Composer")

        if state.replan_attempts > 0:
            st.warning(f"Replans: {state.replan_attempts}")


st.title("Multi-Agent Trip Planner")
st.markdown("Describe your trip and the agents will plan it for you.")


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


if st.session_state.pending_input is not None:
    user_input = st.session_state.pending_input
    st.session_state.pending_input = None

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        workflow = st.session_state.workflow

        completed_nodes: list[str] = []
        failed_nodes: list[str] = []
        debug_events = []
        latest_logs = []
        agent_outputs = {}

        with st.status("Planning your trip...", expanded=True) as status:
            live_line = st.empty()
            completed_line = st.empty()
            debug_timeline = st.container()

            if hasattr(workflow, "stream_events"):
                for event in workflow.stream_events(user_input):
                    event_type = event.get("event", "")
                    node = event.get("node", "")
                    message = event.get("message", "")
                    elapsed = event.get("elapsed")
                    snapshot = event.get("snapshot")
                    icon = _event_icon(event_type)

                    if event_type == "start":
                        live_line.markdown(f"{icon} **Running:** `{node}`")
                        status.write(f"{icon} Running **{node}**...")

                    elif event_type == "done":
                        completed_nodes.append(node)

                        if elapsed is not None:
                            live_line.markdown(
                                f"{icon} **Completed:** `{node}` in `{elapsed}s`"
                            )
                            status.write(
                                f"{icon} Completed **{node}** in `{elapsed}s`"
                            )
                        else:
                            live_line.markdown(f"{icon} **Completed:** `{node}`")
                            status.write(f"{icon} Completed **{node}**")

                        if snapshot:
                            agent_outputs[node] = snapshot

                            with st.expander(
                                f"{icon} Output from {node}",
                                expanded=False,
                            ):
                                st.json(snapshot)

                    elif event_type == "skip":
                        status.write(f"{icon} Skipped **{node}** — {message}")

                        if snapshot:
                            agent_outputs[node] = snapshot

                            with st.expander(
                                f"{icon} Existing output from {node}",
                                expanded=False,
                            ):
                                st.json(snapshot)

                    elif event_type == "warning":
                        status.write(f"{icon} {message}")

                    elif event_type == "error":
                        failed_nodes.append(node)

                        if elapsed is not None:
                            status.write(
                                f"{icon} **{node}** failed after `{elapsed}s` — {message}"
                            )
                        else:
                            status.write(f"{icon} **{node}** failed — {message}")

                        if snapshot:
                            agent_outputs[node] = snapshot

                            with st.expander(
                                f"{icon} Partial output from {node}",
                                expanded=False,
                            ):
                                st.json(snapshot)

                    elif event_type == "info":
                        status.write(f"{icon} {message}")

                        if snapshot:
                            with st.expander(
                                f"{icon} Info snapshot",
                                expanded=False,
                            ):
                                st.json(snapshot)

                    elif event_type == "complete":
                        completed = event.get("completed", [])

                        completed_line.markdown(
                            "**Completed nodes:** "
                            + ", ".join(f"`{item}`" for item in completed)
                        )

                        if snapshot:
                            with st.expander(
                                f"{icon} Workflow summary",
                                expanded=False,
                            ):
                                st.json(snapshot)

                    decision_log = event.get("decision_log", [])

                    if decision_log:
                        latest_logs = decision_log

                    debug_events.append(event)

                    with debug_timeline:
                        if event_type in [
                            "done",
                            "skip",
                            "warning",
                            "error",
                            "info",
                        ]:
                            if elapsed is not None:
                                st.markdown(
                                    f"- {icon} `{node}` — {message} `{elapsed}s`"
                                )
                            else:
                                st.markdown(f"- {icon} `{node}` — {message}")

            else:
                status.write(
                    "⚠️ `stream_events()` not found. Falling back to basic stream."
                )

                step_container = st.empty()

                for node in workflow.stream(user_input):
                    completed_nodes.append(node)
                    step_container.markdown(f"✅ `{node}` complete")
                    status.write(f"✅ `{node}` complete")

            result = workflow.get_state()

            if failed_nodes:
                status.update(
                    label="Trip planning completed with some failed agents.",
                    state="error",
                    expanded=True,
                )
            else:
                status.update(
                    label="Trip planning completed.",
                    state="complete",
                    expanded=False,
                )

        if agent_outputs:
            with st.expander("All Agent Outputs", expanded=True):
                st.json(agent_outputs)

        if latest_logs:
            with st.expander("Latest Decision Log", expanded=False):
                for log in latest_logs:
                    st.markdown(f"- {log}")

        if debug_events:
            with st.expander("Raw Debug Events", expanded=False):
                st.json(debug_events)

        if result is not None:
            _render_result(result)

            assistant_content = _build_assistant_message(result)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": assistant_content,
                }
            )

        else:
            error_message = "No result was produced."
            st.error(error_message)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": error_message,
                }
            )


user_input = st.chat_input(
    "Describe your trip (e.g., 'Plan a 5 day trip to Jaipur in December, budget 25000 rupees')"
)

if user_input:
    st.session_state.pending_input = user_input
    st.rerun()