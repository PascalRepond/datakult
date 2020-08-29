from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from djrichtextfield.models import RichTextField

from django.db import models

# Create your models here.

class Activity(models.Model) :
  user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_('user'),
                          blank=True, null=True, on_delete=models.CASCADE)
  content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
  object_id = models.PositiveIntegerField(_('object id'))
  content_object = GenericForeignKey('content_type', 'object_id')

  rating = models.PositiveSmallIntegerField(_('rating'), blank=True, null=True)
  review = RichTextField(_('review'), blank=True, null=True)

  date_started = models.DateField(_('started'), blank=True, null=True)
  date_finished = models.DateField(_('finished'), blank=True, null=True)

  class Meta:
    verbose_name = "activity"
    verbose_name_plural = "activities"