from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from .models import Vendor
from .serializers import VendorSerializer


class VendorViewSet(ModelViewSet):
    queryset = Vendor.objects.all().order_by("name")
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
