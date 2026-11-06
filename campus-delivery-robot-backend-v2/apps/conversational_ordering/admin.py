from django.contrib import admin

from .models import AIConversationTurn


@admin.register(AIConversationTurn)
class AIConversationTurnAdmin(admin.ModelAdmin):
    list_display = ("id", "session_id", "policy", "action", "latency_ms", "created_at")
    list_filter = ("policy", "action", "created_at")
    search_fields = ("session_id", "transcript")
    readonly_fields = (
        "session_id",
        "transcript",
        "draft_order",
        "validation",
        "signals",
        "action",
        "policy",
        "latency_ms",
        "token_usage",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
