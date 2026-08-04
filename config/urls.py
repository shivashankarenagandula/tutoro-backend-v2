"""
Root URL configuration for Tutoro.
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import ThrottledTokenObtainPairView

urlpatterns = [
    path("admin/", admin.site.urls),

    # JWT auth -- login/refresh work out of the box since User.USERNAME_FIELD
    # is already 'email'; no custom serializer needed for this part.
    # Login uses ThrottledTokenObtainPairView (not simplejwt's bare
    # TokenObtainPairView) so brute-force password guessing is rate
    # limited -- see apps/accounts/views.py LoginThrottle.
    path("api/auth/login/", ThrottledTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/auth/", include("apps.accounts.urls")),  # register/parent, register/tutor

    path("api/catalog/", include("apps.catalog.urls")),   # cities, areas, subjects
    path("api/profiles/", include("apps.profiles.urls")), # parents/me, tutors/me, tutors/<id>/verify
    path("api/matching/", include("apps.matching.urls")), # requests, assignments, suggest-tutors
    path("api/leads/", include("apps.leads.urls")),        # parent/, tutor/ -- public, from the marketing site
]
