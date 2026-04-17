from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from .models import MenuItem
from .serializers import MenuItemSerializer


class MenuItemViewSet(ModelViewSet):
    queryset = MenuItem.objects.select_related("vendor").all().order_by("name")
    serializer_class = MenuItemSerializer
    permission_classes = [IsAuthenticated]
