import re
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
from .services import parse_customer_turn
from .sessions import cache_key, initial_session


def _redact_contact_details(transcript):
    transcript = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", transcript)
    phone_pattern = r"(?<!\w)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\w)"
    return re.sub(phone_pattern, "[phone]", transcript)


class ParseOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        input_serializer = ParseOrderTurnSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        session_id = input_serializer.validated_data["session_id"]
        transcript = input_serializer.validated_data["transcript"]
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
            result, updated_state = parse_customer_turn(
                session_id, request.user.pk, transcript, state
            )
        except AIProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        result["latency_ms"] = round((perf_counter() - started) * 1000, 2)
        cache.set(key, updated_state, timeout=settings.AI_SESSION_TTL_SECONDS)
        if settings.AI_LOG_TURNS:
            AIConversationTurn.objects.create(
                session_id=session_id,
                transcript=_redact_contact_details(transcript),
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
