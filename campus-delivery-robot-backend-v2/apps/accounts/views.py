from rest_framework.generics import RetrieveAPIView

from .serializers import UserSerializer


class MeView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
