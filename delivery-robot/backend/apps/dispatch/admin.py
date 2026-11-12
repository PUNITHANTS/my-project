from django.contrib import admin

from .models import RobotDispatch


@admin.register(RobotDispatch)
class RobotDispatchAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "status", "updated_at")
    list_filter = ("provider", "status")
