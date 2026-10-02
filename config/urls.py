"""
Main URL Configuration

This module defines the root URL patterns
for the Django project.

All Django Ninja API endpoints are exposed
under the /api/ path.
"""

from django.urls import path

from fuel_optimizer_api.api import api


# ============================================================
# URL Patterns
# ============================================================

urlpatterns = [

    # Django Ninja API
    #
    # Base API URL:
    # /api/
    #
    # Swagger documentation:
    # /api/docs
    #
    # Example endpoint:
    # /api/routes/optimize-fuel

    path(
        "api/",
        api.urls
    ),

]