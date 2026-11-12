from django.contrib import admin

from .models import MenuAvailabilityWindow, MenuItem, MenuOption, MenuOptionGroup


class MenuOptionGroupInline(admin.TabularInline):
    model = MenuOptionGroup
    extra = 0


class MenuAvailabilityWindowInline(admin.TabularInline):
    model = MenuAvailabilityWindow
    extra = 0


class MenuOptionInline(admin.TabularInline):
    model = MenuOption
    extra = 0


@admin.register(MenuOptionGroup)
class MenuOptionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "menu_item", "is_required", "min_selections", "max_selections")
    list_filter = ("is_required", "menu_item__vendor")
    search_fields = ("name", "menu_item__name")
    inlines = [MenuOptionInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "vendor", "price", "is_available", "max_quantity", "prep_time_minutes")
    list_filter = ("is_available", "vendor")
    search_fields = ("name", "vendor__name")
    inlines = [MenuOptionGroupInline, MenuAvailabilityWindowInline]
