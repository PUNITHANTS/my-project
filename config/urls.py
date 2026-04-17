from django.contrib import admin
from django.urls import include, path
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


@api_view(["GET"])
@permission_classes([AllowAny])
def healthcheck(_request):
    return Response({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", healthcheck, name="healthcheck"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/vendors/", include("apps.vendors.urls")),
    path("api/menu/", include("apps.menu.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/dispatch/", include("apps.dispatch.urls")),
]
