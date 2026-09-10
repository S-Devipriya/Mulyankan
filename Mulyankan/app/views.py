from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.views.decorators.clickjacking import xframe_options_sameorigin
from app.decorators import admin_required
from django.db import IntegrityError
from app.models import AssignmentSubmission, EvaluationResult
from pathlib import Path

# Create your views here.
User = get_user_model()

def welcome(request):
    return render(request,'welcome.html')

def register_user(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username','').strip()
        email = request.POST.get('email','').strip()
        password = request.POST.get('password','')

        if not username or not password or not email:
            messages.error(request, 'Please enter all details.')
            return render(request, 'register.html')

        try:
            #create_user() automatically hashes password unlike create()
            User.objects.create_user(
                username = username,
                email = email,
                password = password
            )
            messages.success(request, 'Registration successful. Please log in.')
            return redirect('login')
        except IntegrityError:
            messages.error(request, 'A user with that username or email already exists.')
    
    return render(request, 'register.html')

def login_user(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)  # 2 weeks in seconds
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid email or password. Please try again.')
    
    return render(request, 'login.html')

@require_POST
def logout_user(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')

@login_required
def dashboard(request):
    assignments = {
        'assignment': AssignmentSubmission.objects.all()
    }
    return render(request, 'dashboard.html', assignments)

@login_required
def result_page(request):
    results = {
        'result': EvaluationResult.objects.select_related('submission').all(),
    }
    return render(request, 'result.html', results)

def view_assignment(request, pk):
    submissions = {
        'submission': get_object_or_404(AssignmentSubmission, pk=pk)
    }
    return render(request, 'assignment.html', submissions)

@xframe_options_sameorigin
def stream_assignment_pdf(request, pk):
    submission = get_object_or_404(AssignmentSubmission, pk=pk)
    clean_path = submission.file_path.lstrip('/\\')
    full_path = Path(settings.BASE_DIR) / clean_path
    resolved_path = full_path.resolve()
    base_dir = Path(settings.BASE_DIR).resolve()
    
    if not resolved_path.is_relative_to(base_dir) or not resolved_path.is_file():
        raise Http404("File not found.")
    
    return FileResponse(open(resolved_path, 'rb'), content_type='application/pdf')

@admin_required
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')
