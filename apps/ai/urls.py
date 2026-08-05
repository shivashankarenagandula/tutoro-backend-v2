from django.urls import path

from .views import FAQChatView

urlpatterns = [
    path("faq/", FAQChatView.as_view(), name="ai-faq"),
]
