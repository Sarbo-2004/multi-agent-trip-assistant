"""
Persistent memory for the LangGraph trip planner.

Stores TripState and conversation history as JSON files,
one file per conversation thread.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver

from config.settings import settings
from models.trip_state import TripState


MEMORY_DIR = settings.BASE_DIR / "graph" / "data" / "threads"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def get_checkpointer() -> MemorySaver:
    """
    Return LangGraph's in-memory checkpointer.

    Persistent storage is handled separately by TripMemory.
    """
    return MemorySaver()


class TripMemory:
    """
    JSON-based persistent memory.

    Each thread is stored as:

    graph/memory/<thread_id>.json

    Structure:

    {
        "trip_state": {...},
        "messages": [
            {
                "role": "...",
                "content": "..."
            }
        ]
    }
    """

    def _path(self, thread_id: str) -> Path:
        return MEMORY_DIR / f"{thread_id}.json"

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------

    def _load_file(self, thread_id: str) -> dict:
        path = self._path(thread_id)

        if not path.exists():
            return {
                "trip_state": None,
                "messages": [],
            }

        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save_file(
        self,
        thread_id: str,
        data: dict,
    ) -> None:
        path = self._path(thread_id)

        with path.open("w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False,
            )

    # ---------------------------------------------------------
    # TripState
    # ---------------------------------------------------------

    def save_state(
        self,
        thread_id: str,
        state: TripState,
    ) -> None:
        """Persist TripState."""

        data = self._load_file(thread_id)

        data["trip_state"] = state.model_dump(mode="json")

        self._save_file(
            thread_id,
            data,
        )

    def load_state(
        self,
        thread_id: str,
    ) -> Optional[TripState]:
        """Load TripState."""

        data = self._load_file(thread_id)

        state = data.get("trip_state")

        if state is None:
            return None

        return TripState.model_validate(state)

    # ---------------------------------------------------------
    # Conversation History
    # ---------------------------------------------------------

    def save_message(
        self,
        thread_id: str,
        role: str,
        content: str,
    ) -> None:
        """Append a conversation message."""

        data = self._load_file(thread_id)

        data["messages"].append(
            {
                "role": role,
                "content": content,
            }
        )

        self._save_file(
            thread_id,
            data,
        )

    def load_history(
        self,
        thread_id: str,
    ) -> list[dict[str, str]]:
        """Return conversation history."""

        data = self._load_file(thread_id)

        return data.get("messages", [])

    # ---------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------

    def delete_thread(
        self,
        thread_id: str,
    ) -> None:
        """Delete a conversation."""

        path = self._path(thread_id)

        if path.exists():
            path.unlink()

    def thread_exists(
        self,
        thread_id: str,
    ) -> bool:
        """Check if a thread exists."""

        return self._path(thread_id).exists()