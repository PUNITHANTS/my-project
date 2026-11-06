import json
import urllib.error
import urllib.request

from django.conf import settings
from pydantic import ValidationError

from .schemas import ParsedOrder


class AIProviderError(Exception):
    """A safe, user-facing error from the configured LLM provider."""


SYSTEM_PROMPT = """You convert one customer turn into a structured campus food-order draft.
Return only a JSON object matching the requested fields. Use only menu_item_id values
from the supplied menu. Preserve every existing line the customer did not change.
Attach each customization to its specific line item. Never invent menu items or
options. Use null for an unknown item ID or delivery location. Confidence values
must be between 0 and 1. Do not place an order; a person must confirm the final cart.
"""


def interpret_turn(transcript, menu, current_draft, messages, temperature=0):
    if not settings.GROQ_API_KEY:
        raise AIProviderError("The backend is missing GROQ_API_KEY.")
    if not settings.GROQ_MODEL or settings.GROQ_MODEL == "your-active-groq-model-id":
        raise AIProviderError("Set GROQ_MODEL to an active model in the backend environment.")

    payload_for_model = {
        "customer_turn": transcript,
        "current_draft": current_draft,
        "recent_conversation": messages[-8:],
        "live_menu": menu,
        "required_output_fields": {
            "items": [
                {
                    "menu_item_id": "menu UUID or null",
                    "mention": "customer wording",
                    "quantity": 1,
                    "customizations": ["offered option names only"],
                    "confidence": {"item": 0.0, "quantity": 0.0, "customization": 0.0},
                }
            ],
            "delivery_location": "string or null",
            "confidence": 0.0,
            "delivery_location_confidence": 0.0,
            "clarification_needed": "question or null",
        },
    }
    request_body = {
        "model": settings.GROQ_MODEL,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload_for_model)},
        ],
    }

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    for attempt in range(2):
        body = dict(request_body)
        if attempt:
            body["messages"] = request_body["messages"] + [
                {
                    "role": "user",
                    "content": "Your previous response failed schema validation. Return the exact JSON fields requested.",
                }
            ]
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "campus-delivery-ordering/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
            usage = result.get("usage") or {}
            total_usage["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
            total_usage["completion_tokens"] += int(usage.get("completion_tokens", 0))
            content = result["choices"][0]["message"]["content"]
            return ParsedOrder.model_validate_json(content), total_usage
        except ValidationError:
            if attempt == 0:
                continue
            return None, total_usage
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404, 422):
                raise AIProviderError(
                    "Groq rejected the model or request configuration. Check GROQ_MODEL and JSON mode support."
                ) from exc
            if exc.code == 401:
                message = "Groq rejected GROQ_API_KEY (HTTP 401). Check that the backend key is active."
            elif exc.code == 403:
                message = "Groq denied this request (HTTP 403). Check API access or network proxy settings."
            elif exc.code == 429:
                message = "Groq rate or quota limit reached (HTTP 429). Wait and check account limits."
            elif exc.code >= 500:
                message = f"Groq is temporarily unavailable (HTTP {exc.code}). Try again shortly."
            else:
                message = f"Groq rejected the request (HTTP {exc.code}). Check account access."
            raise AIProviderError(message) from exc
        except (
            KeyError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise AIProviderError("The AI provider is unavailable or returned an unreadable response.") from exc
        except urllib.error.URLError as exc:
            raise AIProviderError(
                "The backend could not reach Groq. Check outbound HTTPS, DNS, or proxy settings."
            ) from exc
        except TimeoutError as exc:
            raise AIProviderError("Groq did not respond before the request timed out.") from exc

    return None
