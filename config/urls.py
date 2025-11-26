"""
URL configuration for Squid Digest project.
"""
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse


def health_check(request):
    """Simple health check endpoint."""
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health'),
]
