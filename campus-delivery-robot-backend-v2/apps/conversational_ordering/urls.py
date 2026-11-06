from django.urls import path

from .views import ParseOrderView


urlpatterns = [
    path("parse-order/", ParseOrderView.as_view(), name="parse-order"),
]
