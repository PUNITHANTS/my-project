def cache_key(session_id):
    return f"conversational-order:{session_id}"


def initial_session(user_id):
    return {
        "user_id": user_id,
        "messages": [],
        "draft_order": None,
        "asked_slots": [],
        "questions_asked": 0,
        "submitted_order_id": None,
    }
