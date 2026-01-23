from django.urls import path
from . import views  # import the entire views.py module

urlpatterns = [
    path("", views.landing_page, name="landing"),
    path("login/", views.login_view, name="login"),
    path("dashboard/", views.dashboard, name="dashboard"),
      path("logout/", views.logout_view, name="logout"),
]
