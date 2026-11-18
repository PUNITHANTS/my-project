import re
import uuid
from time import perf_counter

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .groq_client import AIProviderError
from .models import AIConversationTurn
from .serializers import ParseOrderTurnSerializer
from .services import (
    InvalidTurnInput,
    apply_cart_edit,
    apply_selected_option,
    parse_customer_turn,
    provider_error_result,
)
from .sessions import cache_key, initial_session


def _redact_contact_details(transcript):
    transcript = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", transcript)
    phone_pattern = r"(?<!\w)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\w)"
    return re.sub(phone_pattern, "[phone]", transcript)


class ParseOrderView(APIView):
    """One kiosk turn: typed text, a tapped option, or a cart edit.

    Only typed text reaches the model; options and edits are applied in code.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        input_serializer = ParseOrderTurnSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        session_id = data["session_id"]
        input_kind = data["input_kind"]
        turn_id = uuid.uuid4()
        key = cache_key(session_id)
        state = cache.get(key)
        if state is None:
            state = initial_session(request.user.pk)
        elif state.get("user_id") != request.user.pk:
            raise PermissionDenied("This conversation belongs to another user.")
        if state.get("submitted_order_id"):
            return Response(
                {"detail": "This conversation has already been submitted. Start a new session."},
                status=status.HTTP_409_CONFLICT,
            )

        started = perf_counter()
        try:
            if input_kind == "selected_option":
                result, updated_state = apply_selected_option(
                    session_id, request.user.pk, data["selected_option"], state
                )
            elif input_kind == "cart_edit":
                result, updated_state = apply_cart_edit(
                    session_id, request.user.pk, data["cart_edit"], state
                )
            else:
                result, updated_state = parse_customer_turn(
                    session_id, request.user.pk, data["transcript"], state
                )
        except InvalidTurnInput as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AIProviderError as exc:
            result = provider_error_result(session_id, state, str(exc))
            result["turn_id"] = str(turn_id)
            return Response(result)

        result["turn_id"] = str(turn_id)
        result["latency_ms"] = round((perf_counter() - started) * 1000, 2)
        cache.set(key, updated_state, timeout=settings.AI_SESSION_TTL_SECONDS)
        if settings.AI_LOG_TURNS:
            # Direct turns log the text the service recorded, e.g. "[selected] Large".
            logged_text = updated_state["messages"][-2]["content"]
            AIConversationTurn.objects.create(
                turn_id=turn_id,
                input_kind=input_kind,
                session_id=session_id,
                transcript=_redact_contact_details(logged_text),
                draft_order={
                    "items": result["items"],
                    "vendor_id": result["vendorId"],
                    "delivery_location": result["deliveryLocation"],
                },
                validation={
                    "policy": result["validation"],
                    "safety": result["raw_validation"],
                },
                signals=result["signals"],
                action=result["action"],
                policy=result["policy"],
                latency_ms=result["latency_ms"],
                token_usage=result["token_usage"],
            )
        return Response(result)
