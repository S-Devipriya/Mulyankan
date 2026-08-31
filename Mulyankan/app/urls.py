from django.urls import path
from django.urls import include
from.import views

urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('register', views.register),
    path('login', views.login, name='login'),
]