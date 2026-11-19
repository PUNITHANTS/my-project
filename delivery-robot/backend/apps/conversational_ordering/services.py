import re

from django.conf import settings
from django.core import signing

from .canonicalize import canonicalize_draft
from .groq_client import AIProviderError, interpret_turn
from .menu_validation import load_menu_catalog, names_item, normalize_text, validate_draft
from .policies import choose_clarification_policy
from .questions import (
    REMOVE_CUSTOMIZATION,
    clarification_options,
    question_line,
    repair_options,
)
from .schemas import ParsedOrder


CONFIRMATION_SALT = "campus-delivery-ai-confirmation-v1"


class InvalidTurnInput(Exception):
    """A tapped option or cart edit that does not fit the current draft."""


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
    return names_item(transcript, menu_item["name"])


def _is_asked_line(old_item, asked_line):
    return bool(asked_line) and (
        str(old_item.get("menu_item_id")) == asked_line["menu_item_id"]
        and old_item.get("mention") == asked_line["mention"]
    )


def _preserve_untouched(previous, parsed, transcript, catalog, asked_line=None):
    """Put back lines the model dropped or changed although the customer did not.

    ``asked_line`` is the line the previous question was about. The customer's
    answer is allowed to replace or change it ("which burger?" -> "a grilled
    chicken burger"), so it is never restored.
    """
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
    # "Change that to three spicy burgers": the old line is swapped, not kept.
    replace_cue = bool(re.search(r"\b(change|switch|swap|replace|instead)\b", normalized_transcript))
    preservation_notes = []
    old_ids = {str(item.get("menu_item_id")) for item in old_items}
    # The answer brought in a line that was not there before: the asked-about
    # line was replaced, not lost.
    has_replacement = any(item_id not in old_ids for item_id in new_by_id)

    for old_item in old_items:
        item_id = str(old_item.get("menu_item_id"))
        menu_item = catalog_by_id.get(item_id)
        explicitly_touched = bool(
            (menu_item and _explicitly_mentions(transcript, menu_item))
            or _is_asked_line(old_item, asked_line)
        )
        can_apply_reference = generic_reference and len(old_items) == 1
        current = new_by_id.get(item_id)

        if current is None:
            if removal and (explicitly_touched or can_apply_reference):
                continue
            if has_replacement and _is_asked_line(old_item, asked_line):
                continue
            if has_replacement and replace_cue and (explicitly_touched or can_apply_reference):
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


def _cart_output(parsed, catalog, vendor_id):
    """The cart in the kiosk contract's shape; ``line`` is the slot index."""
    by_id = {item["id"]: item for item in catalog}
    vendor_name = next(
        (item["vendor"] for item in catalog if item["vendor_id"] == vendor_id), None
    )
    return {
        "items": [
            {
                "line": index,
                "menuItemId": item.menu_item_id,
                "name": by_id.get(str(item.menu_item_id), {}).get("name", item.mention),
                "quantity": item.quantity,
                "customization": ", ".join(item.customizations),
                "customizations": item.customizations,
                "unitPrice": by_id.get(str(item.menu_item_id), {}).get("price"),
            }
            for index, item in enumerate(parsed.items)
        ],
        "vendorId": vendor_id,
        "vendorName": vendor_name,
        "deliveryLocation": parsed.delivery_location,
    }


def _decide(
    session_id,
    user_id,
    parsed,
    state,
    catalog,
    configuration,
    user_text,
    usage,
    agreement=0.0,
    preservation_notes=(),
    llm_called=True,
):
    """Validate a draft, choose the next action and build the turn response.

    Shared by LLM turns and by the LLM-free turns (tapped option, cart edit), so
    every draft the kiosk sees has passed the same checks.
    """
    configuration = (configuration or settings.AI_DEFAULT_POLICY).upper()
    safety_validation = validate_draft(
        parsed,
        catalog,
        settings.AI_NEAR_MATCH_THRESHOLD,
        state.get("resolved_item_ids", ()),
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

    signals = _signals(parsed, validation, agreement)
    policy_result = choose_clarification_policy(configuration, signals, validation)
    question = None
    options = []
    if validation["violations"] and configuration != "C1":
        action = "REPAIR"
        question = _repair_question(validation)
        options = repair_options(validation, parsed, catalog)
    elif (validation["missing_details"] and configuration != "C1") or policy_result["ask"]:
        action = "ASK"
        question = _clarification_question(parsed, validation, signals)
        options = clarification_options(validation)
    else:
        action = "CONFIRM"

    questions_asked = state.get("questions_asked", 0)
    budget_exhausted = bool(question and questions_asked >= settings.AI_MAX_QUESTIONS)
    if budget_exhausted:
        action = "ESCALATE"
        options = []
        question = (
            "I could not safely resolve this order within the clarification limit. "
            "Please review the cart or contact the vendor before ordering."
        )

    state["asked_line"] = None
    if action in ("ASK", "REPAIR") and question:
        questions_asked += 1
        state.setdefault("asked_slots", []).append(question)
        line_index = question_line(action, validation)
        if line_index is not None and line_index < len(parsed.items):
            asked = parsed.items[line_index]
            state["asked_line"] = {
                "menu_item_id": str(asked.menu_item_id),
                "mention": asked.mention,
            }

    valid_for_submission = (
        safety_validation["valid"] and not safety_validation["missing_details"]
    )
    vendor_id = validation.get("vendor_id")
    public_draft = _draft_output(parsed, catalog, vendor_id)
    token = None
    if action == "CONFIRM" and valid_for_submission and vendor_id:
        token = confirmation_token(session_id, user_id, parsed, vendor_id)

    message = question or "Please review the cart and confirm."
    state["draft_order"] = parsed.model_dump(mode="json")
    state["messages"] = (state.get("messages", []) + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": message},
    ])[-16:]
    state["questions_asked"] = questions_asked
    # Only these options may come back as selected_option on the next turn.
    state["offered_options"] = options
    result = {
        **public_draft,
        "session_id": str(session_id),
        "message": message,
        "options": options,
        "cart": _cart_output(parsed, catalog, vendor_id),
        "llm_called": llm_called,
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
        "preservation_checks": list(preservation_notes),
        "confirmation_token": token,
        "token_usage": usage,
    }
    return result, state


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

    parsed, usage = interpret_turn(transcript, catalog, prior_draft, prior_messages)
    if parsed is None:
        parsed = ParsedOrder(
            items=[],
            delivery_location=(prior_draft or {}).get("delivery_location"),
            confidence=0.0,
            delivery_location_confidence=0.0,
            clarification_needed="I could not interpret that request. Could you rephrase it?",
        )
    parsed, preservation_notes = _preserve_untouched(
        prior_draft, parsed, transcript, catalog, state.get("asked_line")
    )
    parsed, canonical_notes = canonicalize_draft(parsed, transcript, catalog, prior_draft)
    preservation_notes = list(preservation_notes) + canonical_notes
    # Items the customer has called by their full name are settled; the
    # validator stops offering look-alikes for them.
    by_id = {item["id"]: item for item in catalog}
    named = {
        str(line.menu_item_id)
        for line in parsed.items
        if str(line.menu_item_id) in by_id
        and _explicitly_mentions(transcript, by_id[str(line.menu_item_id)])
    }
    if named:
        state["resolved_item_ids"] = sorted(set(state.get("resolved_item_ids", [])) | named)

    agreement, sample_usage = _sample_agreement(
        parsed,
        catalog,
        prior_draft,
        prior_messages,
        transcript,
        settings.AI_SAMPLE_AGREEMENT_K,
    )
    for key in usage:
        usage[key] += sample_usage[key]

    return _decide(
        session_id,
        user_id,
        parsed,
        state,
        catalog,
        configuration,
        transcript,
        usage,
        agreement=agreement,
        preservation_notes=preservation_notes,
    )


def _stored_draft(state):
    draft = state.get("draft_order")
    if not draft:
        raise InvalidTurnInput("There is no order in progress to change.")
    return ParsedOrder.model_validate(draft).model_dump(mode="json")


def _line(draft, index):
    if not 0 <= index < len(draft["items"]):
        raise InvalidTurnInput("That cart line no longer exists.")
    return draft["items"][index]


def _slot_line(slot):
    try:
        return int(slot.split(":", 1)[1])
    except (IndexError, ValueError) as exc:
        raise InvalidTurnInput("Unknown option slot.") from exc


def _apply_customization(line, menu_item, value):
    offered = {
        normalize_text(option)
        for group in menu_item["option_groups"]
        for option in group["options"]
    }
    # Selections the menu does not offer are what the repair question was about.
    kept = [name for name in line["customizations"] if normalize_text(name) in offered]
    if value != REMOVE_CUSTOMIZATION:
        group = next(
            (
                group
                for group in menu_item["option_groups"]
                if normalize_text(value)
                in {normalize_text(option) for option in group["options"]}
            ),
            None,
        )
        if group is None:
            raise InvalidTurnInput("That option is no longer offered.")
        in_group = {normalize_text(option) for option in group["options"]}
        same_group = [name for name in kept if normalize_text(name) in in_group]
        # Make room so the tapped option never exceeds the group's limit.
        overflow = len(same_group) + 1 - group["max_selections"]
        for name in same_group[: max(overflow, 0)]:
            kept.remove(name)
        if normalize_text(value) not in {normalize_text(name) for name in kept}:
            kept.append(value)
    line["customizations"] = kept
    line["confidence"]["customization"] = 1.0


def _finish_direct_turn(session_id, user_id, draft, state, catalog, configuration, user_text):
    # The model's own question was about the previous draft; code has changed it.
    draft["clarification_needed"] = None
    return _decide(
        session_id,
        user_id,
        ParsedOrder.model_validate(draft),
        state,
        catalog,
        configuration,
        user_text,
        {"prompt_tokens": 0, "completion_tokens": 0},
        llm_called=False,
    )


def apply_selected_option(
    session_id, user_id, selected, state, configuration=None, catalog_override=None
):
    """Apply a tapped option to the draft in code, with no LLM call."""
    offered = next(
        (
            option
            for option in state.get("offered_options", [])
            if option["slot"] == selected.get("slot")
            and option.get("menuItemId") == selected.get("menuItemId")
            and option.get("value") == selected.get("value")
        ),
        None,
    )
    if offered is None:
        raise InvalidTurnInput(
            "That option is no longer available. Please answer the latest question."
        )

    catalog = catalog_override if catalog_override is not None else load_menu_catalog()
    by_id = {item["id"]: item for item in catalog}
    draft = _stored_draft(state)
    slot = offered["slot"]
    kind = slot.split(":", 1)[0]

    if kind == "location":
        draft["delivery_location"] = offered["value"]
        draft["delivery_location_confidence"] = 1.0
    elif kind == "vendor":
        draft["items"] = [
            line
            for line in draft["items"]
            if str(by_id.get(str(line["menu_item_id"]), {}).get("vendor_id"))
            == offered["value"]
        ]
    elif kind == "item":
        line = _line(draft, _slot_line(slot))
        menu_item = by_id.get(offered["menuItemId"])
        if menu_item is None:
            raise InvalidTurnInput("That menu item is no longer available.")
        if line["menu_item_id"] != menu_item["id"]:
            # Customizations chosen for a different item may not exist on this one.
            line["customizations"] = []
        line["menu_item_id"] = menu_item["id"]
        line["mention"] = menu_item["name"]
        line["confidence"]["item"] = 1.0
        resolved = set(state.get("resolved_item_ids", []))
        resolved.add(menu_item["id"])
        state["resolved_item_ids"] = sorted(resolved)
    elif kind == "option":
        line = _line(draft, _slot_line(slot))
        menu_item = by_id.get(str(line["menu_item_id"]))
        if menu_item is None:
            raise InvalidTurnInput("That menu item is no longer available.")
        _apply_customization(line, menu_item, offered["value"])
    elif kind == "quantity":
        line = _line(draft, _slot_line(slot))
        line["quantity"] = int(offered["value"])
        line["confidence"]["quantity"] = 1.0
    else:
        raise InvalidTurnInput("Unknown option slot.")

    return _finish_direct_turn(
        session_id,
        user_id,
        draft,
        state,
        catalog,
        configuration,
        f"[selected] {offered['label']}",
    )


def apply_cart_edit(
    session_id, user_id, edit, state, configuration=None, catalog_override=None
):
    """Change a line's quantity, or remove it with quantity 0, with no LLM call."""
    catalog = catalog_override if catalog_override is not None else load_menu_catalog()
    draft = _stored_draft(state)
    line = _line(draft, edit["line"])
    name = next(
        (item["name"] for item in catalog if item["id"] == str(line["menu_item_id"])),
        line["mention"],
    )
    if edit["quantity"] == 0:
        draft["items"].remove(line)
        user_text = f"[cart edit] removed {name}"
    else:
        line["quantity"] = edit["quantity"]
        line["confidence"]["quantity"] = 1.0
        user_text = f"[cart edit] {name} x {edit['quantity']}"
    return _finish_direct_turn(
        session_id, user_id, draft, state, catalog, configuration, user_text
    )


def provider_error_result(session_id, state, detail):
    """The ERROR turn the kiosk gets when the model cannot be reached.

    It carries the cart as it stood, so the kiosk can hand it to the touch menu.
    """
    catalog = load_menu_catalog()
    draft = state.get("draft_order")
    parsed = (
        ParsedOrder.model_validate(draft)
        if draft
        else ParsedOrder(
            items=[],
            delivery_location=None,
            confidence=0.0,
            delivery_location_confidence=0.0,
        )
    )
    line_item_ids = {str(line.menu_item_id) for line in parsed.items}
    vendor_ids = {item["vendor_id"] for item in catalog if item["id"] in line_item_ids}
    vendor_id = next(iter(vendor_ids)) if len(vendor_ids) == 1 else None
    return {
        **_draft_output(parsed, catalog, vendor_id),
        "session_id": str(session_id),
        "action": "ERROR",
        "message": "The ordering assistant is unavailable right now. Please order from the menu.",
        "detail": detail,
        "options": [],
        "cart": _cart_output(parsed, catalog, vendor_id),
        "llm_called": True,
        "confidence": 0.0,
        "clarificationNeeded": None,
        "valid_for_submission": False,
        "confirmation_token": None,
    }
