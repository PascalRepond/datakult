from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from djrichtextfield.models import RichTextField

from django.db import models

# Create your models here.

class Activity(models.Model) :

  STATUS = [
    (0, _('In wishlist')),
    (1, _('Under way')),
    (2, _('Done')),
    (3, _('Abandoned')),
    (4, _('Finished')),
  ]

  RATINGS = [
    (1, _('Detested')),
    (2, _('Hated')),
    (3, _('Didn\'t like')),
    (4, _('Didn\'t really like')),
    (5, _('Moderately enjoyed')),
    (6, _('Enjoyed')),
    (7, _('Liked')),
    (8, _('Liked a lot')),
    (9, _('Loved')),
    (10, _('Adored')),
  ]

  ''' Foreign keys (work/user) '''
  user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_('user'),
    blank=True, null=True, on_delete=models.CASCADE)
  content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
  object_id = models.PositiveIntegerField(_('object id'))
  content_object = GenericForeignKey('content_type', 'object_id')

  status = models.PositiveSmallIntegerField(
    _('status'),
    choices=STATUS,
    blank=True, null=True)

  rating = models.PositiveSmallIntegerField(_('rating'), choices=RATINGS, blank=True, null=True)
  review = RichTextField(_('review'), blank=True, null=True)

  date_started = models.DateField(_('started'), blank=True, null=True)
  date_finished = models.DateField(_('finished'), blank=True, null=True)

  class Meta:
    verbose_name = "activity"
    verbose_name_plural = "activities"