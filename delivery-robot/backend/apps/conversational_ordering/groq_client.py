import hashlib
import http.client
import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from pydantic import ValidationError

from .schemas import ParsedOrder

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """A safe, user-facing error from the configured LLM provider."""


SYSTEM_PROMPT = """You convert one customer turn into a structured campus food-order draft.
Return only a JSON object matching the requested fields. Use only menu_item_id values
from the supplied menu. Preserve every existing line the customer did not change.
Attach each customization to its specific line item. Never invent menu items or
options. Use null for an unknown item ID or delivery location. Confidence values
must be between 0 and 1. Do not place an order; a person must confirm the final cart.
"""


def _post_with_rate_limit_retry(request):
    headers = {key: value for key, value in request.header_items()}
    parsed = urlparse(request.full_url)
    path = parsed.path or "/"
    data = request.data
    # Offline experiments wait out rate limits; a kiosk customer cannot, so live
    # requests retry once and give up quickly (the kiosk then offers the menu).
    tries = 8 if settings.AI_EXPERIMENT_MODE else 2
    timeout = 120 if settings.AI_EXPERIMENT_MODE else 20
    for rate_try in range(tries):
        # Plain HTTP is allowed so a local OpenAI-compatible server (Ollama,
        # llama.cpp) can serve the same open-weight model for experiments.
        connection_class = (
            http.client.HTTPConnection if parsed.scheme == "http" else http.client.HTTPSConnection
        )
        connection = connection_class(parsed.hostname, parsed.port, timeout=timeout)
        try:
            connection.request("POST", path, body=data, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            if response.status == 429 and rate_try < tries - 1:
                retry_after = response.getheader("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else 2 ** rate_try
                except ValueError:
                    delay = 2 ** rate_try
                time.sleep(min(max(delay, 1), 20))
                continue
            if response.status >= 500 and settings.AI_EXPERIMENT_MODE and rate_try < tries - 1:
                # Ollama returns 500 "token repeat limit reached" when greedy
                # (temperature 0) decoding loops; the same request loops again on
                # every retry. Retry with a small seeded temperature so the run
                # continues and stays reproducible. Live requests never do this.
                logger.warning(
                    "Model server returned %s (%s); retrying with seeded temperature.",
                    response.status,
                    payload[:200].decode("utf-8", "replace"),
                )
                body = json.loads(data.decode("utf-8"))
                body.update({"temperature": 0.3, "seed": rate_try + 1})
                data = json.dumps(body).encode("utf-8")
                time.sleep(1)
                continue
            if response.status >= 400:
                raise urllib.error.HTTPError(
                    request.full_url, response.status, response.reason, response.headers, None
                )
            return json.loads(payload.decode("utf-8"))
        except urllib.error.HTTPError:
            raise
        except (ConnectionResetError, TimeoutError, BrokenPipeError, OSError):
            if rate_try >= tries - 1:
                raise
            time.sleep(min(2 ** rate_try, 20))
            continue
        finally:
            connection.close()
    raise AIProviderError("The model provider rate or quota limit was reached (HTTP 429). Wait and retry.")


def compact_menu(menu):
    """One short line per item: about a quarter of the tokens of the full JSON.

    Only what the model needs to pick items and options is kept; prices, limits
    and availability windows are enforced by the validator, not the model.
    """
    lines = []
    for item in menu:
        groups = "; ".join(
            f"{group['name']} ({'required' if group['required'] else 'optional'}): "
            + ", ".join(group["options"])
            for group in item["option_groups"]
        )
        line = f"{item['id']} | {item['name']} | {item['vendor']}"
        if groups:
            line += f" | {groups}"
        if not item["available"]:
            line += " | UNAVAILABLE"
        lines.append(line)
    return lines


def compact_draft(draft):
    if not draft:
        return None
    return {
        "items": [
            {
                "menu_item_id": item.get("menu_item_id"),
                "mention": item.get("mention"),
                "quantity": item.get("quantity"),
                "customizations": item.get("customizations", []),
            }
            for item in draft.get("items", [])
        ],
        "delivery_location": draft.get("delivery_location"),
    }


def _cache_path(body):
    directory = getattr(settings, "AI_RESPONSE_CACHE_DIR", None)
    if not directory or body.get("temperature"):
        # Sampled calls (S5 agreement) must stay independent, so never cache them.
        return None
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
    return Path(directory) / digest[:2] / f"{digest}.json"


def _complete(request, body):
    """POST one completion, served from the response cache when the same request was made before."""
    path = _cache_path(body)
    if path is not None and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    result = _post_with_rate_limit_retry(request)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result), encoding="utf-8")
    return result


def interpret_turn(transcript, menu, current_draft, messages, temperature=0):
    if not settings.LLM_API_KEY:
        raise AIProviderError("The backend is missing an LLM API key.")
    if not settings.GROQ_MODEL or settings.GROQ_MODEL == "your-active-groq-model-id":
        raise AIProviderError("Set GROQ_MODEL to an active model in the backend environment.")

    payload_for_model = {
        "customer_turn": transcript,
        "current_draft": compact_draft(current_draft),
        "recent_conversation": messages[-6:],
        "menu": compact_menu(menu),
        "menu_format": "id | name | vendor | option group (required/optional): options",
        "required_output_fields": {
            "items": [
                {
                    "menu_item_id": "menu id or null",
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
    if "gpt-oss" in settings.GROQ_MODEL:
        request_body["reasoning_effort"] = "low"

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
            settings.LLM_API_BASE,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "campus-delivery-ordering/1.0",
            },
            method="POST",
        )
        try:
            result = _complete(request, body)
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
                    "The model provider rejected the request configuration. Check the model id and JSON mode support."
                ) from exc
            if exc.code == 401:
                message = "The model provider rejected the API key (HTTP 401)."
            elif exc.code == 403:
                message = "The model provider denied this request (HTTP 403)."
            elif exc.code == 429:
                message = "The model provider rate or quota limit was reached (HTTP 429)."
            elif exc.code >= 500:
                message = f"The model provider is temporarily unavailable (HTTP {exc.code})."
            else:
                message = f"The model provider rejected the request (HTTP {exc.code})."
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
                "The backend could not reach the model provider. Check outbound HTTPS, DNS, or proxy settings."
            ) from exc
        except TimeoutError as exc:
            raise AIProviderError("The model provider did not respond before the request timed out.") from exc

    return None
