from django.urls import path

from .views import OrderViewSet


order_list = OrderViewSet.as_view({"get": "list", "post": "create_order"})
order_detail = OrderViewSet.as_view({"get": "retrieve"})
order_status = OrderViewSet.as_view({"post": "update_status"})

urlpatterns = [
    path("", order_list, name="orders-list-create"),
    path("<int:pk>/", order_detail, name="orders-detail"),
    path("<int:pk>/status/", order_status, name="orders-status"),
]
