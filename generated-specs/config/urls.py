from django.urls import path

from app import views

urlpatterns = [
    path("health", views.health),
    path("api/v1/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework/<str:aggregate_id>/<str:command>", views.execute),
]
