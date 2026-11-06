from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import AdminOrManagedVendorWrite, is_project_admin

from .models import Vendor
from .serializers import VendorSerializer


class VendorViewSet(ModelViewSet):
    queryset = Vendor.objects.all().order_by("name")
    serializer_class = VendorSerializer
    permission_classes = [AdminOrManagedVendorWrite]

    def get_queryset(self):
        # Students need vendor discovery; write permissions remain owner-scoped.
        return super().get_queryset()

    def perform_create(self, serializer):
        if not is_project_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only an administrator can create a vendor.")
        serializer.save()

    def perform_update(self, serializer):
        if not is_project_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied

            if "manager" in serializer.validated_data:
                raise PermissionDenied("Only an administrator can reassign a vendor manager.")
        serializer.save()
