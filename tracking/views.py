from django.views.generic import CreateView

from .models import Activity

class ActivityCreate(CreateView):
  model = Activity
  fields = ['status', 'rating', 'review', 'date_started', 'date_finished']
  template_name = 'tracking/activitycreate.html'