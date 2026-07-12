from rest_framework.routers import DefaultRouter

from .views import AreaViewSet, CityViewSet, SubjectViewSet

router = DefaultRouter()
router.register("cities", CityViewSet, basename="city")
router.register("areas", AreaViewSet, basename="area")
router.register("subjects", SubjectViewSet, basename="subject")

urlpatterns = router.urls
