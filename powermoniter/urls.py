"""
URL configuration for powermoniter project.

The `urlpatterns` list routes URLs to views.
"""

from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

from apps.api.errors import ApiError, api_error_handler
from apps.api.routes.device_api import router as device_api_router

api = NinjaAPI(
    title="Power Moniter API",
    version="1.0.0",
    docs_url="/docs/",  # API 文档入口
)
api.add_exception_handler(ApiError, api_error_handler)
api.add_router("/v1/devices", device_api_router)


urlpatterns = [
    path("admin/", admin.site.urls),
]
