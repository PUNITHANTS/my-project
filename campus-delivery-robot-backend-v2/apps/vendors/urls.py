from rest_framework.routers import DefaultRouter

from .views import VendorViewSet


router = DefaultRouter()
router.register("", VendorViewSet, basename="vendors")

urlpatterns = router.urls
