from django.urls import path

from .views import RegisterParentView, RegisterTutorView

urlpatterns = [
    path("register/parent/", RegisterParentView.as_view(), name="register-parent"),
    path("register/tutor/", RegisterTutorView.as_view(), name="register-tutor"),
]
