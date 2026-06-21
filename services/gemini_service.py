"""
Gemini Service – wrapper around Google Gemini.

This service is responsible only for communicating with the Gemini API.
It does not contain any business logic. Agents provide the prompts and
interpret the responses.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import json
from config.settings import settings


class GeminiService:
    """Simple wrapper around the Gemini API."""

    def __init__(self) -> None:
        if settings.GEMINI_API_KEY is None:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        self._client = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY.get_secret_value(),
            temperature=0.2,
            max_output_tokens=4096,
            streaming=False,
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send prompts to Gemini and return the generated response.

        Args:
            system_prompt: Instructions defining Gemini's role.
            user_prompt: Input prompt for the current task.

        Returns:
            The generated text response.

        Raises:
            RuntimeError: If the Gemini API call fails.
        """
        try:
            response = self._client.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )

            return response.content.strip()

        except Exception as e:
            raise RuntimeError(f"Gemini API call failed: {e}") from e
    
    
    @staticmethod
    def parse_json(text: str) -> dict:
        """Parse JSON from Gemini response, handling common formatting issues."""
        text = text.strip()

        # Remove markdown code fences
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON object from text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse JSON from response: {text[:200]}...")