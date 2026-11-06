from django.contrib import admin

from .models import Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("previous_status", "status", "actor", "note", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "student_name", "vendor", "status", "delivery_location", "created_at")
    list_filter = ("status", "vendor")
    search_fields = ("student_name", "phone", "delivery_location")
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    readonly_fields = ("status", "created_at", "updated_at")
