from django.urls import path
from django.urls import include
from.import views

urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('register', views.register_user, name='register'),
    path('login', views.login_user, name='login'),
    path('evaluator-dashboard/', views.evaluator_dashboard, name='evaluator_dashboard'),
    path('evaluator-dashboard/evaluate/<int:submission_id>/', views.evaluate_submission, name='evaluate_submission'),
    path('evaluator-dashboard/evaluating/<int:submission_id>/', views.retrigger_evaluation, name="retrigger_evaluation"),
    path('logout', views.logout_user, name='logout'),
    path('result', views.result_page, name='result'),
    path('assignment/<int:pk>/pdf/', views.view_assignment, name='view_assignment'),
    path('assignment/<int:pk>/stream/', views.stream_assignment_pdf, name='stream_assignment_pdf'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('registration_waiting_page', views.registration_waiting, name='registration_waiting_page'),
    path('admin-dashboard/assign-evaluator/', views.assign_evaluator, name='assign_evaluator'),
    path('admin-dashboard/update-expertise/', views.update_evaluator_expertise, name='update_evaluator_expertise'),
    path('admin-dashboard/upload-batchwise-assignments/', views.upload_batchwise_assignments, name='upload_batchwise_assignments'),
    path('admin-dashboard/upload-textbooks/', views.upload_textbooks, name="upload_textbooks"),
    path('admin-dashboard/extract-submissions/', views.run_extract_submissions, name='run_extract_submissions'),
    path('admin-dashboard/ingest-textbooks/', views.run_ingest_textbooks, name='run_ingest_textbooks'),
    path('admin-dashboard/run-batch-evaluation/', views.run_batch_evaluation, name='run_batch_evaluation'),
    path('admin-dashboard/update-courses-json/', views.update_courses_json, name='update_courses_json'),
    path('admin-dashboard/update-assignment-schemes-json/', views.update_assignment_schemes_json, name='update_assignment_schemes_json'),
]