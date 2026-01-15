from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse, HttpResponseNotFound
from django.urls import include, path, re_path
from django.views.static import serve


def service_worker(_request):
    """Serve the service worker at the root scope."""
    sw_path = settings.BASE_DIR / "static" / "js" / "service-worker.js"
    try:
        with sw_path.open() as f:
            return HttpResponse(f.read(), content_type="application/javascript")
    except (FileNotFoundError, PermissionError):
        return HttpResponseNotFound("Service worker not found")


urlpatterns = [
    path("service-worker.js", service_worker, name="service_worker"),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    # Include django_browser_reload URLs only in DEBUG mode
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
    # Serve media files in development using Django's static helper
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Serve media files in production using django.views.static.serve
    # It works well for small to medium deployments (< 10k files, < 100 concurrent users)
    # For high-traffic production, consider using nginx or a CDN instead
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
