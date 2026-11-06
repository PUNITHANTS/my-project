from rest_framework.routers import DefaultRouter

from .views import MenuItemViewSet


router = DefaultRouter()
router.register("items", MenuItemViewSet, basename="menu-items")

urlpatterns = router.urls
