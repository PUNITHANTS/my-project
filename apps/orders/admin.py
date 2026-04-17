from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "student_name", "vendor", "status", "delivery_location", "created_at")
    list_filter = ("status", "vendor")
    search_fields = ("student_name", "phone", "delivery_location")
    inlines = [OrderItemInline]
