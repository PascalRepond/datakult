from django.urls import path

from .views import ActivityCreate

urlpatterns = [
  path('<str:contenttype>/<int:pk>/create', ActivityCreate.as_view(), name='activity_create')
]