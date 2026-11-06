from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import RobotDispatch
from .serializers import RobotDispatchSerializer


class RobotDispatchViewSet(ReadOnlyModelViewSet):
    queryset = RobotDispatch.objects.select_related("order").all().order_by("-created_at")
    serializer_class = RobotDispatchSerializer
    permission_classes = [IsAuthenticated]
