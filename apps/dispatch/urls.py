from rest_framework.routers import DefaultRouter

from .views import RobotDispatchViewSet


router = DefaultRouter()
router.register("", RobotDispatchViewSet, basename="dispatch")

urlpatterns = router.urls
