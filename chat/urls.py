from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("setup", views.setup, name="setup"),
    path("search_page", views.search_page, name="search_page"),
    path("feedback_page", views.feedback_page, name="feedback_page"),
    #path("search", views.search, name="search"),
]
