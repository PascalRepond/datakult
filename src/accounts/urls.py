from django.urls import path
from django.views.i18n import set_language

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.profile_edit, name="profile_edit"),
    path("profile/validate-profile/", views.validate_profile_field, name="validate_profile_field"),
    path("profile/validate-password/", views.validate_password_field, name="validate_password_field"),
    path("set-language/", set_language, name="set_language"),
]
