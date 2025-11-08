"""AI summarization module for generating broadcast scripts."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_generate_briefing(
    hass: HomeAssistant,
    data: list[dict[str, Any]],
    greeting: str,
    max_per_category: int,
    mode: str,
    agent_id: str,
) -> str:
    """Generate a broadcast-style script using AI services.

    Args:
        hass: Home Assistant instance
        data: List of category dicts with articles
        greeting: Time-based greeting (morning/afternoon/night)
        max_per_category: Maximum articles per category
        mode: AI mode ("auto", "google_generative_ai_conversation", "conversation")
        agent_id: Conversation agent ID if mode is "conversation"

    Returns:
        Generated script text

    Raises:
        RuntimeError: If AI service is unavailable or fails
    """
    # Build the JSON payload
    payload = json.dumps(data, indent=2)

    # Compose the prompt
    prompt = f"""You are an expert broadcast writer. Use ONLY the following JSON of fresh Google News items to write a single spoken news script.

JSON: {payload}

Rules:

- Greet: 'Good {greeting},'

- For each category in order, if it has at least 1 article, say: 'in the world of <Category>,'

  then for each article (max {max_per_category} per category) write one concise paragraph:

  first a 5–12 word title-style summary, then a one-paragraph summary using only the provided text.

- Between articles say exactly: 'Next up,'

- Keep each article summary to one short paragraph. No bullets. No links. No sources.

- Do not invent facts. If a category has no articles, skip it.

- Output plain text only."""

    # Try to determine which service to use
    use_google_genai = False
    if mode == "google_generative_ai_conversation":
        use_google_genai = True
    elif mode == "auto":
        # Check if google_generative_ai_conversation service exists
        if hass.services.has_service("google_generative_ai_conversation", "generate_content"):
            use_google_genai = True

    # Call the appropriate service
    if use_google_genai:
        try:
            response = await hass.services.async_call(
                "google_generative_ai_conversation",
                "generate_content",
                {"prompt": prompt},
                blocking=True,
                return_response=True,
            )
            # Extract text from response
            if isinstance(response, dict):
                text = response.get("text", "")
                if text:
                    return text.strip()
            elif isinstance(response, list) and len(response) > 0:
                # Handle list response
                first = response[0]
                if isinstance(first, dict):
                    text = first.get("text", "")
                    if text:
                        return text.strip()
            _LOGGER.warning("Unexpected response format from google_generative_ai_conversation")
            raise RuntimeError("Failed to extract text from AI response")
        except Exception as err:
            _LOGGER.error("Error calling google_generative_ai_conversation: %s", err)
            raise RuntimeError(f"AI service error: {err}") from err

    elif mode == "conversation":
        if not agent_id:
            raise RuntimeError("conversation_agent_id is required when ai_mode is 'conversation'")

        try:
            response = await hass.services.async_call(
                "conversation",
                "process",
                {
                    "agent_id": agent_id,
                    "text": prompt,
                },
                blocking=True,
                return_response=True,
            )
            # Extract speech from response
            if isinstance(response, dict):
                speech = response.get("speech", {})
                if isinstance(speech, dict):
                    plain = speech.get("plain", {})
                    if isinstance(plain, dict):
                        text = plain.get("speech", "")
                        if text:
                            return text.strip()
            _LOGGER.warning("Unexpected response format from conversation.process")
            raise RuntimeError("Failed to extract speech from conversation response")
        except Exception as err:
            _LOGGER.error("Error calling conversation.process: %s", err)
            raise RuntimeError(f"Conversation service error: {err}") from err

    else:
        raise RuntimeError(
            f"Invalid ai_mode '{mode}'. Enable google_generative_ai_conversation integration "
            "or configure a conversation agent_id."
        )

