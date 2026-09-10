from django.urls import path
from django.urls import include
from.import views

urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('register', views.register_user, name='register'),
    path('login', views.login_user, name='login'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('logout', views.logout_user, name='logout'),
    path('result', views.result_page, name='result'),
    path('assignment/<int:pk>/pdf/', views.view_assignment, name='view_assignment'),
    path('assignment/<int:pk>/stream/', views.stream_assignment_pdf, name='stream_assignment_pdf'),
    path('admin-dashboard', views.admin_dashboard, name='admin_dashboard'),
]