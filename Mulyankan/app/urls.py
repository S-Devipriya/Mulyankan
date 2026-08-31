from django.urls import path
from django.urls import include
from.import views

urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('register', views.register_user, name='register'),
    path('login', views.login_user, name='login'),
]