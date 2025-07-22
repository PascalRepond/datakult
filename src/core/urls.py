from django.urls import include, path
from rest_framework.routers import DefaultRouter

from core import views

router = DefaultRouter()
router.register(r"media", views.MediaViewset, basename="media")
router.register(r"agents", views.AgentViewset, basename="agent")

urlpatterns = [
    path("", include(router.urls)),
]
