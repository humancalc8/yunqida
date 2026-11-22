
import json

from django.conf import settings
from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    Groq,
    RateLimitError,
)


class GroqAIError(Exception):
    """Raised when the Groq AI service cannot complete a request."""


def get_groq_client():
    """
    Create a Groq client using the API key configured in Django settings.
    """

    api_key = getattr(settings, "GROQ_API_KEY", "")

    if not api_key:
        raise GroqAIError(
            "Groq API key is missing. Check your GROQ_API_KEY setting."
        )

    return Groq(
        api_key=api_key,
        timeout=60.0,
        max_retries=2,
    )


def groq_chat(
    messages,
    max_completion_tokens=2000,
    response_format=None,
):
    """
    Send a conversation to Groq and return the assistant's response.

    Args:
        messages: List of role/content message dictionaries.
        max_completion_tokens: Maximum response token allowance.
        response_format: Optional format, e.g. {"type": "json_object"}.

    Returns:
        Assistant response as a string.

    Raises:
        GroqAIError: If the request fails or returns no usable content.
    """

    if not isinstance(messages, list) or not messages:
        raise GroqAIError("A non-empty messages list is required.")

    try:
        client = get_groq_client()

        request_options = {
            "model": settings.GROQ_MODEL,
            "messages": messages,
            "max_completion_tokens": max_completion_tokens,
        }

        if response_format:
            request_options["response_format"] = response_format

        response = client.chat.completions.create(**request_options)

        if not response.choices:
            raise GroqAIError("Groq returned an empty response.")

        content = response.choices[0].message.content

        if not content:
            raise GroqAIError("Groq returned no text content.")

        return content.strip()

    except GroqAIError:
        raise

    except RateLimitError as exc:
        raise GroqAIError(
            "Groq rate limit reached. Please try again shortly."
        ) from exc

    except APITimeoutError as exc:
        raise GroqAIError(
            "The AI service took too long to respond. Please try again."
        ) from exc

    except APIConnectionError as exc:
        raise GroqAIError(
            "Could not connect to the Groq AI service. Check your internet connection."
        ) from exc

    except APIStatusError as exc:
        raise GroqAIError(
            f"Groq API returned an error (HTTP {exc.status_code})."
        ) from exc

    except Exception as exc:
        raise GroqAIError(
            "An unexpected error occurred while contacting the AI service."
        ) from exc


def groq_chat_json(messages, max_completion_tokens=4000):
    """
    Request a JSON response from Groq and return the parsed Python object.
    """

    content = groq_chat(
        messages=messages,
        max_completion_tokens=max_completion_tokens,
        response_format={"type": "json_object"},
    )

    try:
        return json.loads(content)

    except json.JSONDecodeError as exc:
        raise GroqAIError(
            "The AI returned an invalid JSON response. Please try again."
        ) from exc
