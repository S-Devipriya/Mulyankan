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
from app.decorators import admin_required, evaluator_required
from django.db import IntegrityError, transaction
from app.models import AssignmentSubmission, EvaluationResult, EvaluationBatch, EvaluatorExpertise, Course
from app.services.pipeline import evaluate_submission_pipeline
from app.services.plagiarism_checker import generate_course_peer_map
from pathlib import Path
from django.utils import timezone
import threading
import json, csv
import zipfile

# Create your views here.
User = get_user_model()

def welcome(request):
    return render(request,'welcome.html')

def register_user(request):
    if request.user.is_authenticated:
        if request.user.role == 'Evaluator':
            return redirect('evaluator_dashboard')
        elif request.user.role == 'Admin' or request.user.is_superuser:
            return redirect('admin_dashboard')
        else:
            return redirect('registration_waiting_page')
    
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
        if request.user.role == 'Evaluator':
            return redirect('evaluator_dashboard')
        elif request.user.role == 'Admin' or request.user.is_superuser:
            return redirect('admin_dashboard')
        else:
            return redirect('registration_waiting_page')

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
                return redirect('evaluator_dashboard')
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

    schemes_file = settings.BASE_DIR / 'data' / 'assignment_schemes.json'
    schemes_map = {}
    if schemes_file.exists():
        with open(schemes_file, 'r', encoding='utf-8') as f:
            try:
                schemes_map = json.load(f)
            except json.JSONDecodeError:
                schemes_map = {}

    results_by_batch = {}

    for batch in EvaluationBatch.objects.all():
        batch_submissions = AssignmentSubmission.objects.filter(batch=batch)
        
        # Selecting batches with no assignments left for review
        if batch_submissions.exists() and not batch_submissions.filter(status='Pending Review').exists():
            results = EvaluationResult.objects.filter(
                submission__batch=batch
            ).select_related('submission__course', 'submission__evaluator')
            
            results_by_batch[batch.id] = {
                'batch_id': batch.id,
                'batch_name': batch.batch_name,
                'results': list(results)
            }

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
        'scheme_course_codes': list(schemes_map.keys()),
        'schemes_json_map': json.dumps(schemes_map),
        'result': EvaluationResult.objects.select_related('submission').all(),
        'results_by_batch': results_by_batch.values(),
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

@admin_required
def run_batch_evaluation(request):
    if request.method == 'POST':
        batch_id = request.POST.get('batch_id')
        
        if not batch_id:
            messages.error(request, "Please select a valid batch to evaluate.")
            return redirect('admin_dashboard')

        batch = get_object_or_404(EvaluationBatch, id=batch_id, status='Processing')
        pending_submissions = AssignmentSubmission.objects.filter(
            batch=batch, 
            status='Pending Review'
        )

        if not pending_submissions.exists():
            messages.warning(request, f"No pending submissions found in batch '{batch.batch_name}'.")
            return redirect('admin_dashboard')

        submission_ids = list(pending_submissions.values_list('id', flat=True))

        # Background Execution Thread
        def process_batch_pipeline(sub_ids):
            submissions = AssignmentSubmission.objects.filter(id__in=sub_ids).select_related('course')
            course_codes = set(s.course.course_code for s in submissions if s.course)

            # Step 1: Pre-compute peer plagiarism map across extracted_text
            peer_maps_by_course = {}
            for course_code in course_codes:
                peer_maps_by_course[course_code] = generate_course_peer_map(course_code, batch_id, min_threshold=50.0)

            # Step 2: Run pipeline.py with real pre-computed peer data
            for sub in submissions:
                try:
                    c_code = sub.course.course_code if sub.course else ""
                    c_peer_map = peer_maps_by_course.get(c_code, {})
                    
                    evaluate_submission_pipeline(sub.id, peer_map=c_peer_map)
                except Exception as e:
                    print(f"[PIPELINE BATCH ERROR] Failed evaluating submission ID {sub.id}: {e}")
                finally:
                    batch.status = 'Ready'
                    batch.save(update_fields=['status'])

        thread = threading.Thread(target=process_batch_pipeline, args=(submission_ids,))
        thread.start()

        messages.success(request, f"Started background AI evaluation for {len(submission_ids)} pending submission(s) in batch '{batch.batch_name}'.")

    return redirect('admin_dashboard')

@admin_required
def update_courses_json(request):
    if request.method == 'POST':
        code = request.POST.get('course_code', '').strip().upper()
        name = request.POST.get('course_name', '').strip()

        if code and name:
            file_path = settings.BASE_DIR / 'data' / 'courses.json'
            courses_data = {}

            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        courses_data = json.load(f)
                    except json.JSONDecodeError:
                        courses_data = {}

            courses_data[code] = {'course_name': name}

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(courses_data, f, indent=4)

            messages.success(request, f"Course '{code}' saved to courses.json.")

    return redirect('admin_dashboard')

@admin_required
def update_assignment_schemes_json(request):
    if request.method == 'POST':
        code = request.POST.get('course_code', '').strip().upper()
        total_marks = float(request.POST.get('total_marks', 0.0))

        # Retrieve array lists from submitted form
        q_keys = request.POST.getlist('question_keys[]')
        max_marks_list = request.POST.getlist('max_marks_list[]')
        q_texts = request.POST.getlist('question_texts[]')

        if code and q_keys:
            file_path = settings.BASE_DIR / 'data' / 'assignment_schemes.json'
            schemes_data = {}

            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        schemes_data = json.load(f)
                    except json.JSONDecodeError:
                        schemes_data = {}

            # Initialize or retain existing course entry
            if code not in schemes_data:
                schemes_data[code] = {'total_marks': total_marks, 'questions': {}}
            else:
                schemes_data[code]['total_marks'] = total_marks
                if 'questions' not in schemes_data[code]:
                    schemes_data[code]['questions'] = {}

            # Map all submitted question rows into the JSON structure
            for key, max_m, text in zip(q_keys, max_marks_list, q_texts):
                key_str = key.strip()
                if key_str and text.strip():
                    schemes_data[code]['questions'][key_str] = {
                        'max_marks': float(max_m) if max_m else 0.0,
                        'question_text': text.strip()
                    }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(schemes_data, f, indent=4)

            messages.success(request, f"Updated scheme for '{code}' with {len(q_keys)} question(s).")

    return redirect('admin_dashboard')

@admin_required
def export_results_csv(request, batch_id=None):
    response = HttpResponse(content_type='text/csv')
    
    if batch_id:
        batch = get_object_or_404(EvaluationBatch, id=batch_id)
        response['Content-Disposition'] = f'attachment; filename="mulyankan_results_{batch.batch_name}.csv"'
        results = EvaluationResult.objects.filter(submission__batch=batch)
    else:
        response['Content-Disposition'] = 'attachment; filename="mulyankan_results_all.csv"'
        results = EvaluationResult.objects.all()

    results = results.select_related('submission__batch', 'submission__course')

    writer = csv.writer(response)
    writer.writerow(['Enrollment Number', 'Course Code', 'Batch Name', 'Evaluator', 'Final Score'])

    for res in results:
        writer.writerow([
            res.submission.enrollment_number,
            res.submission.course.course_code,
            res.submission.batch.batch_name,
            res.submission.evaluator.username,
            res.human_final_score if res.human_final_score is not None else 'Pending'
        ])

    return response

@evaluator_required
def evaluator_dashboard(request):
    user = request.user
    
    #retrieves all submissions assigned to this evaluator
    assigned_submissions = AssignmentSubmission.objects.filter(evaluator=user).select_related('batch', 'course').order_by('batch__batch_name', 'id')

    #groups submissions by EvaluationBatch
    batch_queue = {}
    for sub in assigned_submissions:
        batch_id = sub.batch.id
        if batch_id not in batch_queue:
            batch_queue[batch_id] = {
                'batch_name': sub.batch.batch_name,
                'batch_status': sub.batch.status,
                'pending_submissions': [],
                'reviewed_submissions': [],
                'pending_count': 0,
                'reviewed_count': 0,
            }
        
        batch_queue[batch_id]['pending_submissions'].append(sub) if sub.status == 'Pending Review' else batch_queue[batch_id]['reviewed_submissions'].append(sub)
        if sub.status == 'Pending Review':
            batch_queue[batch_id]['pending_count'] += 1
        else:
            batch_queue[batch_id]['reviewed_count'] += 1

    context = {
        'batch_queue': batch_queue.values(),
        'total_assigned': assigned_submissions.count(),
        'total_pending': assigned_submissions.filter(status='Pending Review').count(),
        'total_reviewed': assigned_submissions.filter(status='Reviewed').count(),
    }
    return render(request, 'dashboard/evaluator_dashboard.html', context)

@evaluator_required
def evaluate_submission(request, submission_id):
    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related('course', 'batch'), 
        id=submission_id, 
        evaluator=request.user
    )
    
    result = getattr(submission, 'evaluation_result', None)

    batch_submissions = list(
        AssignmentSubmission.objects.filter(
            batch=submission.batch, 
            evaluator=request.user
        ).values_list('id', flat=True).order_by('id')
    )
    
    current_idx = batch_submissions.index(submission.id)
    prev_id = batch_submissions[current_idx - 1] if current_idx > 0 else None
    next_id = batch_submissions[current_idx + 1] if current_idx < len(batch_submissions) - 1 else None

    total_max_marks = sum(item.get('max_marks', 0) for item in result.audit_logic)

    if request.method == "POST":
        if submission.status == 'Reviewed':
            messages.warning(request, "This evaluation is already finalized and cannot be modified.")
            return redirect('evaluate_submission', submission_id=submission.id)
        try:
            human_score = float(request.POST.get('human_final_score', 0))
        except ValueError:
            human_score = -1
        remarks = request.POST.get('evaluator_remarks', 'No remarks provided').strip()

        if human_score < 0 or human_score > total_max_marks:
            messages.error(request, f"Score must be between 0 and {total_max_marks}.")
            return redirect('evaluate_submission', submission_id=submission.id)

        if result and human_score:
            result.human_final_score = float(human_score)
            result.evaluator_remarks = remarks
            result.reviewed_at = timezone.now()
            result.save()

            submission.status = 'Reviewed'
            submission.save()

            batch = submission.batch
            if batch and not AssignmentSubmission.objects.filter(batch=batch, status='Pending Review').exists():
                batch.status = 'Completed'
                batch.save(update_fields=['status'])

            messages.success(request, f"Evaluation saved for Enrollment #{submission.enrollment_number}.")

            #auto-advance to next submission in batch if available
            if next_id:
                return redirect('evaluate_submission', submission_id=next_id)
            return redirect('evaluator_dashboard')

    context = {
        'submission': submission,
        'result': result,
        'prev_id': prev_id,
        'next_id': next_id,
        'audit_logic': result.audit_logic if result else [],
        'total_max_marks': total_max_marks,
    }
    return render(request, 'dashboard/evaluation_splitview.html', context)

@login_required
def registration_waiting(request):
    return render(request, 'registration_waiting_page.html')
