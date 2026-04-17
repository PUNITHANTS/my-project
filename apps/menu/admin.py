from django.contrib import admin

from .models import MenuItem


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "vendor", "price", "is_available", "prep_time_minutes")
    list_filter = ("is_available", "vendor")
    search_fields = ("name", "vendor__name")
