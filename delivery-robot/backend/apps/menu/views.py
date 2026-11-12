from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import AdminOrManagedVendorWrite, is_project_admin

from .models import MenuItem
from .serializers import MenuItemSerializer


class MenuItemViewSet(ModelViewSet):
    queryset = (
        MenuItem.objects.select_related("vendor")
        .prefetch_related("option_groups__options", "availability_windows")
        .all()
        .order_by("name")
    )
    serializer_class = MenuItemSerializer
    permission_classes = [AdminOrManagedVendorWrite]

    def perform_create(self, serializer):
        vendor = serializer.validated_data.get("vendor")
        if not is_project_admin(self.request.user) and vendor.manager_id != self.request.user.pk:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You can only add menu items for your managed vendor.")
        serializer.save()

    def perform_update(self, serializer):
        vendor = serializer.validated_data.get("vendor", serializer.instance.vendor)
        if not is_project_admin(self.request.user) and vendor.manager_id != self.request.user.pk:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You can only edit menu items for your managed vendor.")
        serializer.save()
