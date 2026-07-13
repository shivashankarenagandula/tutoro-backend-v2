"""
catalog.views
--------------
Public, read-only, and — this is the important part — filtered to
is_active=True only. This is what actually enforces "parents can
request tutors only from supported service areas": the frontend's
area dropdown can only ever be populated from this endpoint, and this
endpoint physically cannot return an inactive/out-of-MVP-scope area.

Toggling an area off in Django admin (Area.is_active=False) removes it
from this response immediately — no code change, no redeploy. That's
the "admin can enable/disable areas from the dashboard" requirement.
"""

from rest_framework import permissions, viewsets

from .models import Area, City, Subject
from .serializers import AreaSerializer, CitySerializer, SubjectSerializer


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CitySerializer
    permission_classes = [permissions.AllowAny]
    queryset = City.objects.filter(is_active=True).order_by("name")


class AreaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AreaSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Area.objects.filter(is_active=True, city__is_active=True).select_related("city").order_by("name")


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubjectSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Subject.objects.filter(is_active=True).order_by("name")
