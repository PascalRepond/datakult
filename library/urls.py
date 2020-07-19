from django.urls import path

from .views import WorkListView, WorkDetailView

urlpatterns = [
  path('', WorkListView.as_view(), name='work_list'),
]