from rest_framework.permissions import BasePermission, SAFE_METHODS


def is_project_admin(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser or user.role in ("admin", "superadmin"))
    )


class AdminOrManagedVendorWrite(BasePermission):
    """Allow authenticated reads and writes by admins or the owning vendor."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS or is_project_admin(user):
            return True
        return user.role == "vendor" and user.managed_vendors.exists()

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS or is_project_admin(request.user):
            return True
        vendor = getattr(obj, "vendor", obj)
        return bool(
            request.user.role == "vendor"
            and getattr(vendor, "manager_id", None) == request.user.pk
        )
