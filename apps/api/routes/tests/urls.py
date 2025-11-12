"""Test-only URLConf that exposes the Ninja API routes."""

from __future__ import annotations

from django.contrib import admin
from django.urls import path

from powermoniter.urls import api as ninja_api

urlpatterns = [
    path("admin/", admin.site.urls),
]
urlpatterns.append(path("", ninja_api.urls))  # Expose /v1/devices for test client
