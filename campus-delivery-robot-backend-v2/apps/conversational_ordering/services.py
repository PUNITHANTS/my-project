import re

from django.conf import settings
from django.core import signing

from .groq_client import AIProviderError, interpret_turn
from .menu_validation import load_menu_catalog, normalize_text, validate_draft
from .policies import choose_clarification_policy
from .schemas import ParsedOrder


CONFIRMATION_SALT = "campus-delivery-ai-confirmation-v1"


def _signature_data(parsed, vendor_id):
    return {
        "vendor_id": vendor_id,
        "delivery_location": (parsed.delivery_location or "").strip(),
        "items": sorted(
            [
                {
                    "menu_item_id": str(item.menu_item_id),
                    "quantity": item.quantity,
                    "customization": ", ".join(
                        sorted(normalize_text(value) for value in item.customizations)
                    ),
                }
                for item in parsed.items
            ],
            key=lambda item: (item["menu_item_id"], item["quantity"], item["customization"]),
        ),
    }


def confirmation_token(session_id, user_id, parsed, vendor_id):
    return signing.dumps(
        {
            "session_id": str(session_id),
            "user_id": user_id,
            "cart": _signature_data(parsed, vendor_id),
        },
        salt=CONFIRMATION_SALT,
    )


def confirmed_cart_signature(parsed, vendor_id):
    return _signature_data(parsed, vendor_id)


def submission_cart_signature(vendor_id, delivery_location, items):
    return {
        "vendor_id": int(vendor_id),
        "delivery_location": (delivery_location or "").strip(),
        "items": sorted(
            [
                {
                    "menu_item_id": str(item["menu_item_id"]),
                    "quantity": int(item["quantity"]),
                    "customization": ", ".join(
                        sorted(
                            normalize_text(value)
                            for value in (item.get("customization") or "").split(",")
                            if value.strip()
                        )
                    ),
                }
                for item in items
            ],
            key=lambda item: (item["menu_item_id"], item["quantity"], item["customization"]),
        ),
    }


def _explicitly_mentions(transcript, menu_item):
    words = set(normalize_text(transcript).split())
    name_words = set(normalize_text(menu_item["name"]).split())
    name_words -= {"a", "an", "the", "of", "and"}
    return bool(name_words) and (
        normalize_text(menu_item["name"]) in normalize_text(transcript)
        or (len(name_words) == 1 and name_words.issubset(words))
        or (len(name_words) > 1 and len(name_words & words) >= len(name_words))
    )


def _preserve_untouched(previous, parsed, transcript, catalog):
    if not previous or not previous.get("items"):
        return parsed, []

    catalog_by_id = {item["id"]: item for item in catalog}
    old_items = previous.get("items", [])
    new_data = parsed.model_dump(mode="json")
    new_by_id = {str(item.get("menu_item_id")): item for item in new_data["items"]}
    normalized_transcript = normalize_text(transcript)
    generic_reference = bool(
        re.search(r"\b(that|it|those|same one|last one)\b", normalized_transcript)
        and re.search(r"\b(change|make|switch|remove|add|actually|instead|not)\b", normalized_transcript)
    )
    removal = bool(re.search(r"\b(remove|delete|drop|cancel|without|no longer)\b", normalized_transcript))
    preservation_notes = []

    for old_item in old_items:
        item_id = str(old_item.get("menu_item_id"))
        menu_item = catalog_by_id.get(item_id)
        explicitly_touched = bool(menu_item and _explicitly_mentions(transcript, menu_item))
        can_apply_reference = generic_reference and len(old_items) == 1
        current = new_by_id.get(item_id)

        if current is None:
            if removal and (explicitly_touched or can_apply_reference):
                continue
            new_data["items"].append(old_item)
            preservation_notes.append({"menu_item_id": item_id, "action": "restored_missing_line"})
        elif not explicitly_touched and not can_apply_reference and current != old_item:
            replacement = dict(old_item)
            replacement["confidence"] = current.get("confidence", old_item.get("confidence"))
            new_data["items"] = [
                replacement if str(row.get("menu_item_id")) == item_id else row
                for row in new_data["items"]
            ]
            preservation_notes.append({"menu_item_id": item_id, "action": "restored_untouched_line"})

    old_location = previous.get("delivery_location")
    location_cue = bool(
        re.search(r"\b(to|at|deliver|delivery|location|bring)\b", normalized_transcript)
    )
    if old_location and not location_cue:
        if new_data.get("delivery_location") != old_location:
            new_data["delivery_location"] = old_location
            preservation_notes.append({"slot": "delivery_location", "action": "restored_untouched_value"})

    return ParsedOrder.model_validate(new_data), preservation_notes


def _repair_question(validation):
    if not validation["violations"]:
        return None
    violation = validation["violations"][0]
    if violation["code"] == "missing_location":
        return "Where should I deliver the order?"
    if violation["code"] == "empty_order":
        return "What would you like to order?"
    if violation["code"] == "multiple_vendors":
        return "Items must come from one vendor. Which vendor's items should I keep?"
    if violation["code"] == "invalid_customization":
        alternatives = violation.get("alternatives") or []
        return f"Which available customization would you like: {', '.join(alternatives[:8])}?"
    alternatives = violation.get("alternatives") or []
    if alternatives and isinstance(alternatives[0], dict):
        names = [option["name"] for option in alternatives[:5]]
        return f"{violation['message']} Which would you like: {', '.join(names)}?"
    if alternatives:
        return f"{violation['message']} Available choices: {', '.join(alternatives[:8])}."
    if violation["code"] == "quantity_limit":
        return f"{violation['message']} What quantity would you like instead?"
    return violation["message"]


def _clarification_question(parsed, validation, signals):
    if validation["missing_details"]:
        detail = validation["missing_details"][0]
        choices = ", ".join(detail["choices"][:8])
        return f"Which {detail['group']} would you like for {detail['item_name']}? Available choices: {choices}."
    ambiguous = next(
        (match for match in validation["near_matches"] if match["count"] >= 2), None
    )
    if ambiguous:
        names = ", ".join(item["name"] for item in ambiguous["candidates"][:5])
        return f"Which menu item did you mean by '{ambiguous['mention']}': {names}?"
    if signals["s4"] > 0 and not parsed.items:
        return "What would you like to order?"
    return (parsed.clarification_needed or "Could you clarify your order?")[:300]


def _signals(parsed, validation, sample_agreement):
    slot_confidences = [
        confidence
        for item in parsed.items
        for confidence in (
            item.confidence.item,
            item.confidence.quantity,
            item.confidence.customization,
        )
    ]
    slot_confidences.append(parsed.delivery_location_confidence)
    return {
        "s1": float(parsed.confidence),
        "s2": float(min(slot_confidences, default=parsed.confidence)),
        "s3": float(max((match["count"] for match in validation["near_matches"]), default=0)),
        "s4": float(
            len(validation["missing_details"])
            + (1 if not (parsed.delivery_location or "").strip() else 0)
            + (1 if not parsed.items else 0)
        ),
        "s5": float(sample_agreement),
        "s6": float(sum(1 + len(item.customizations) for item in parsed.items)),
        "s7": float(bool(parsed.clarification_needed)),
    }


def _draft_output(parsed, catalog, vendor_id):
    by_id = {item["id"]: item for item in catalog}
    return {
        "items": [
            {
                "menuItemId": item.menu_item_id,
                "name": by_id.get(str(item.menu_item_id), {}).get("name", item.mention),
                "mention": item.mention,
                "quantity": item.quantity,
                "customizations": item.customizations,
            }
            for item in parsed.items
        ],
        "vendorId": vendor_id,
        "deliveryLocation": parsed.delivery_location,
    }


def _sample_agreement(primary, menu, previous, messages, transcript, sample_count):
    if sample_count <= 0:
        return 0.0, {"prompt_tokens": 0, "completion_tokens": 0}

    expected = primary.model_dump(exclude={"confidence", "delivery_location_confidence"})
    agree = 0
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}
    successful = 0
    for _ in range(sample_count):
        sampled, usage = interpret_turn(
            transcript, menu, previous, messages, temperature=0.7
        )
        for key in usage_total:
            usage_total[key] += usage[key]
        if sampled is None:
            continue
        successful += 1
        sample = sampled.model_dump(exclude={"confidence", "delivery_location_confidence"})
        agree += sample == expected
    return (agree / successful if successful else 0.0), usage_total


def parse_customer_turn(
    session_id,
    user_id,
    transcript,
    state,
    configuration=None,
    catalog_override=None,
):
    catalog = catalog_override if catalog_override is not None else load_menu_catalog()
    prior_messages = state.get("messages", [])
    prior_draft = state.get("draft_order")
    menu_payload = catalog

    parsed, usage = interpret_turn(
        transcript,
        menu_payload,
        prior_draft,
        prior_messages,
    )
    if parsed is None:
        parsed = ParsedOrder(
            items=[],
            delivery_location=(prior_draft or {}).get("delivery_location"),
            confidence=0.0,
            delivery_location_confidence=0.0,
            clarification_needed="I could not interpret that request. Could you rephrase it?",
        )
    parsed, preservation_notes = _preserve_untouched(
        prior_draft, parsed, transcript, catalog
    )

    configuration = (configuration or settings.AI_DEFAULT_POLICY).upper()
    safety_validation = validate_draft(
        parsed, catalog, settings.AI_NEAR_MATCH_THRESHOLD
    )
    validation = safety_validation
    if configuration == "C1":
        validation = {
            "valid": True,
            "violations": [],
            "missing_details": [],
            "near_matches": [],
            "vendor_id": validation["vendor_id"],
        }

    agreement, sample_usage = _sample_agreement(
        parsed,
        menu_payload,
        prior_draft,
        prior_messages,
        transcript,
        settings.AI_SAMPLE_AGREEMENT_K,
    )
    for key in usage:
        usage[key] += sample_usage[key]
    signals = _signals(parsed, validation, agreement)

    policy_result = choose_clarification_policy(configuration, signals, validation)
    question = None
    if validation["violations"] and configuration != "C1":
        action = "REPAIR"
        question = _repair_question(validation)
    elif validation["missing_details"] and configuration != "C1":
        action = "ASK"
        question = _clarification_question(parsed, validation, signals)
    elif policy_result["ask"]:
        action = "ASK"
        question = _clarification_question(parsed, validation, signals)
    else:
        action = "CONFIRM"

    questions_asked = state.get("questions_asked", 0)
    budget_exhausted = bool(question and questions_asked >= settings.AI_MAX_QUESTIONS)
    if budget_exhausted:
        action = "ESCALATE"
        question = (
            "I could not safely resolve this order within the clarification limit. "
            "Please review the cart or contact the vendor before ordering."
        )

    if action in ("ASK", "REPAIR") and question:
        questions_asked += 1
        state.setdefault("asked_slots", []).append(question)

    valid_for_submission = (
        safety_validation["valid"] and not safety_validation["missing_details"]
    )
    public_draft = _draft_output(parsed, catalog, validation.get("vendor_id"))
    token = None
    if action == "CONFIRM" and valid_for_submission and validation.get("vendor_id"):
        token = confirmation_token(
            session_id, user_id, parsed, validation["vendor_id"]
        )

    state["draft_order"] = parsed.model_dump(mode="json")
    state["messages"] = (prior_messages + [
        {"role": "user", "content": transcript},
        {"role": "assistant", "content": question or "Please review the cart and confirm."},
    ])[-16:]
    state["questions_asked"] = questions_asked
    result = {
        **public_draft,
        "session_id": str(session_id),
        "confidence": parsed.confidence,
        "clarificationNeeded": question,
        "model_requested_clarification": bool(parsed.clarification_needed),
        "action": action,
        "validation": validation,
        "raw_validation": safety_validation,
        "valid_for_submission": valid_for_submission,
        "signals": signals,
        "policy": configuration,
        "policy_probability": policy_result["probability"],
        "policy_fallback": policy_result["fallback"],
        "question_budget_exhausted": budget_exhausted,
        "preservation_checks": preservation_notes,
        "confirmation_token": token,
        "token_usage": usage,
    }
    return result, state
