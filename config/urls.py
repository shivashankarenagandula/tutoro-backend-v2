"""
Root URL configuration for Tutoro.
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),

    # JWT auth -- login/refresh work out of the box since User.USERNAME_FIELD
    # is already 'email'; no custom serializer needed for this part.
    path("api/auth/login/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/auth/", include("apps.accounts.urls")),  # register/parent, register/tutor

    path("api/catalog/", include("apps.catalog.urls")),   # cities, areas, subjects
    path("api/profiles/", include("apps.profiles.urls")), # parents/me, tutors/me, tutors/<id>/verify
    path("api/matching/", include("apps.matching.urls")), # requests, assignments, suggest-tutors
]
