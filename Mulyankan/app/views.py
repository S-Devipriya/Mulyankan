from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.management import call_command
from django.views.decorators.clickjacking import xframe_options_sameorigin
from app.decorators import admin_required
from django.db import IntegrityError
from app.models import AssignmentSubmission, EvaluationResult, EvaluationBatch, EvaluatorExpertise, Course
from pathlib import Path
import json
import zipfile

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
            if user.role == 'Evaluator':
                return redirect('dashboard')
            elif user.role == 'Admin' or user.is_superuser:
                return redirect('admin_dashboard')
            else:
                return redirect('registration_waiting_page')
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
    return render(request, 'dashboard/dashboard.html', assignments)

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
    schemes_count = 0
    courses = 0
    textbooks = 0
    try:
        with open(settings.BASE_DIR / 'data/assignment_schemes.json', 'r') as f:
            schemes_data = json.load(f)
            schemes_count = len(schemes_data) if isinstance(schemes_data, dict) or isinstance(schemes_data, list) else 0
    except (FileNotFoundError, json.JSONDecodeError):
        schemes_count = 0

    try:
        with open(settings.BASE_DIR / 'data/courses.json', 'r') as f:
            courses = json.load(f)
            courses = len(courses) if isinstance(courses, dict) or isinstance(courses, list) else 0
    except (FileNotFoundError, json.JSONDecodeError):
        courses = 0

    textbooks_dir = Path(settings.BASE_DIR) / 'data' / 'textbooks'
    textbooks = len([p for p in textbooks_dir.iterdir() if p.is_dir()]) if textbooks_dir.exists() else 0

    assignments_root = Path(settings.BASE_DIR) / 'data' / 'sample_submissions'
    disk_file_count = 0
    if assignments_root.exists():
        #counts all pdf/document files across batch subfolders
        disk_file_count = sum(1 for p in assignments_root.rglob('*') if p.is_file() and not p.name.startswith('.'))
    
    db_submissions_count = AssignmentSubmission.objects.count()
    #unextracted files count
    pending_extraction = max(0, disk_file_count - db_submissions_count)
    pending_allocation = AssignmentSubmission.objects.filter(evaluator__isnull=True).count()
    under_review = EvaluationResult.objects.filter(human_final_score__isnull=True).count()
    evaluated_count = EvaluationResult.objects.filter(human_final_score__isnull=False).count()

    total_eval_batches = EvaluationBatch.objects.count()

    batches_pending_extraction = EvaluationBatch.objects.filter(status='Processing').count()
    batches_active = EvaluationBatch.objects.filter(status='Ready').count()
    batches_ready_to_export = 0
    for batches in EvaluationBatch.objects.all():
        submissions = AssignmentSubmission.objects.filter(batch=batches.id)
        if submissions.exists() and not submissions.filter(status='Pending Review').exists():
            batches_ready_to_export += 1

    evaluators = User.objects.filter(role='Evaluator')
    expertise_map = {}
    for ev in evaluators:
        assigned_courses = EvaluatorExpertise.objects.filter(user=ev).values_list('course_id', flat=True)
        expertise_map[ev.id] = list(assigned_courses)
    unassigned_submissions = AssignmentSubmission.objects.filter(evaluator__isnull=True)

    context = {
        'total_batches': EvaluationBatch.objects.count(),
        'assignments': AssignmentSubmission.objects.count(),
        'total_courses': courses,
        'total_schemes': schemes_count,
        'textbooks': textbooks,
        'assignment_stats': {
            'pending_extraction': pending_extraction,
            'pending_allocation': pending_allocation,
            'under_review': under_review,
            'evaluated': evaluated_count,
        },
        'batch_stats': {
            'total': total_eval_batches,
            'pending_extraction': batches_pending_extraction,
            'active': batches_active,
            'ready_to_export': batches_ready_to_export,
        },
        'evaluators': evaluators,
        'unassigned_submissions': unassigned_submissions,
        'all_courses': Course.objects.all().order_by('course_code'),
        'expertise_map': json.dumps(expertise_map),
        'all_batches': EvaluationBatch.objects.all().order_by('-upload_date'),
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

@admin_required
def assign_evaluator(request):
    if request.method == 'POST':
        submission_id = request.POST.get('submission_id')
        evaluator_id = request.POST.get('evaluator_id')
        
        submission = get_object_or_404(AssignmentSubmission, id=submission_id)
        evaluator = get_object_or_404(User, id=evaluator_id)
        
        submission.evaluator = evaluator
        submission.save()
        
    return redirect('admin_dashboard')

@admin_required
def update_evaluator_expertise(request):
    if request.method == 'POST':
        evaluator_id = request.POST.get('evaluator_id')
        selected_course_ids = request.POST.getlist('course_ids')
        evaluator = get_object_or_404(User, id=evaluator_id, role='Evaluator')

        selected_courses = Course.objects.filter(id__in=selected_course_ids)
        EvaluatorExpertise.objects.filter(user=evaluator).exclude(course__in=selected_courses).delete()
        for course in selected_courses:
            EvaluatorExpertise.objects.get_or_create(user=evaluator, course=course)

        messages.success(request, f"Updated expertise mappings for {evaluator.username}.")

    return redirect('admin_dashboard')

@admin_required
def upload_batchwise_assignments(request):
    if request.method == 'POST' and request.FILES.get('zip_file'):
        batch_name = request.POST.get('batch_name', '').strip()
        zip_file = request.FILES['zip_file']

        if not batch_name:
            messages.error(request, "Batch name is required.")
            return redirect('admin_dashboard')

        #extraction path: data/sample_submissions/<batch_name>/
        target_dir = Path(settings.BASE_DIR) / 'data' / 'sample_submissions' / batch_name
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(target_dir)

            batch, created = EvaluationBatch.objects.get_or_create(
                batch_name=batch_name,
                defaults={'admin': request.user, 'status': 'Processing'}
            )
            
            messages.success(request, f"Batch '{batch_name}' uploaded successfully. Ready for vector extraction.")
        except zipfile.BadZipFile:
            messages.error(request, "Uploaded file is not a valid ZIP archive.")
    return redirect('admin_dashboard')

@admin_required
def upload_textbooks(request):
    if request.method == 'POST' and request.FILES.get('textbook_file'):
        course_id = request.POST.get('course_id')
        uploaded_file = request.FILES['textbook_file']
        
        course = get_object_or_404(Course, id=course_id)
        
        #textbook directory: data/textbooks/<course_code>/
        target_dir = Path(settings.BASE_DIR) / 'data' / 'textbooks' / course.course_code
        target_dir.mkdir(parents=True, exist_ok=True)

        if uploaded_file.name.endswith('.zip'):
            try:
                with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
                messages.success(request, f"Textbook materials extracted for course {course.course_code}.")
            except zipfile.BadZipFile:
                messages.error(request, "Invalid ZIP archive provided.")
        else:
            #single file pdfs
            file_path = target_dir / uploaded_file.name
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            messages.success(request, f"File uploaded for course {course.course_code}.")
    return redirect('admin_dashboard')

@admin_required
def run_extract_submissions(request):
    if request.method == 'POST':
        folder_name = request.POST.get('folder_name', '').strip()
        admin = request.user
        
        try:
            if folder_name:
                #--folder argument to extract_submissions.py
                call_command('extract_submissions', folder=folder_name, admin_username=admin.username)
                messages.success(request, f"Extraction completed for batch '{folder_name}'.")
            else:
                #no argument passed
                call_command('extract_submissions', admin_username=admin.username)
                messages.success(request, "Full submission extraction completed.")
        except Exception as e:
            messages.error(request, f"Error running extract_submissions: {str(e)}")

    return redirect('admin_dashboard')


@admin_required
def run_ingest_textbooks(request):
    if request.method == 'POST':
        course_code = request.POST.get('course_code', '').strip()
        
        try:
            if course_code:
                #--course argument to ingest_textbooks.py
                call_command('ingest_textbooks', course=course_code)
                messages.success(request, f"Textbook ingestion completed for course '{course_code}'.")
            else:
                #no argument passed
                call_command('ingest_textbooks')
                messages.success(request, "Full textbook ingestion completed.")
        except Exception as e:
            messages.error(request, f"Error running ingest_textbooks: {str(e)}")

    return redirect('admin_dashboard')

@login_required
def registration_waiting(request):
    return render(request, 'registration_waiting_page.html')
