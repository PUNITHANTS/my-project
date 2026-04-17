from django.contrib import admin

from .models import Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "location_label", "is_active", "intake_paused")
    list_filter = ("is_active", "intake_paused")
    search_fields = ("name", "location_label")
