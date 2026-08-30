import os
import re
import zipfile
from pathlib import Path
import pymupdf, pymupdf4llm
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from app.models import Course, EvaluationBatch, AssignmentSubmission

User = get_user_model()


class Command(BaseCommand):
    help = 'Parses assignment PDFs from folders or .zip archives into EvaluationBatches and AssignmentSubmissions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--folder',
            type=str,
            help='Subfolder name inside data/sample_submissions/ (folder name becomes batch_name).'
        )
        parser.add_argument(
            '--zip',
            type=str,
            help='Relative path or filename of .zip archive inside data/sample_submissions/.'
        )
        parser.add_argument(
            '--admin-username',
            type=str,
            help='Username of the Admin user creating the batch. Defaults to the first Admin/superuser found.'
        )

    def handle(self, *args, **options):
        folder_arg = options.get('folder')
        zip_arg = options.get('zip')
        admin_username = options.get('admin_username')

        base_submissions_dir = settings.BASE_DIR / 'data' / 'sample_submissions'
        if not base_submissions_dir.exists():
            self.stderr.write(self.style.ERROR(f"Submissions base directory not found at: {base_submissions_dir}"))
            return

        #Resolving Admin User for EvaluationBatch
        admin_user = self._resolve_admin_user(admin_username)
        if not admin_user:
            self.stderr.write(
                self.style.ERROR(
                    "No Admin user found. Please create a user with role='Admin' or specify --admin-username."
                )
            )
            return

        #Zip Ingestion vs Folder Ingestion
        if zip_arg:
            zip_path = Path(zip_arg)
            if not zip_path.is_absolute():
                zip_path = base_submissions_dir / zip_arg

            if not zip_path.exists():
                self.stderr.write(self.style.ERROR(f"Zip file not found at: {zip_path}"))
                return

            batch_name = zip_path.stem
            target_extract_dir = base_submissions_dir / batch_name
            target_extract_dir.mkdir(parents=True, exist_ok=True)

            self.stdout.write(f"Extracting '{zip_path.name}' to permanent directory '{target_extract_dir}'...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_extract_dir)

            self._process_batch_directory(target_extract_dir, batch_name, admin_user)

        elif folder_arg:
            target_dir = base_submissions_dir / folder_arg
            if not target_dir.exists():
                self.stderr.write(self.style.ERROR(f"Target folder not found at: {target_dir}"))
                return

            batch_name = target_dir.name
            self._process_batch_directory(target_dir, batch_name, admin_user)

        else:
            #Process all top-level batch folders found inside data/sample_submissions/
            batch_dirs = [d for d in base_submissions_dir.iterdir() if d.is_dir()]
            if not batch_dirs:
                self.stderr.write(self.style.WARNING(f"No submission folders found in {base_submissions_dir}"))
                return

            for batch_dir in batch_dirs:
                batch_name = batch_dir.name
                self._process_batch_directory(batch_dir, batch_name, admin_user)

    def _process_batch_directory(self, directory: Path, batch_name: str, admin_user):
        pdf_files = list(directory.glob('*.pdf'))
        if not pdf_files:
            self.stderr.write(self.style.WARNING(f"No PDF files found inside {directory}"))
            return

        self.stdout.write(self.style.HTTP_INFO(f"\n--- Initializing Batch: '{batch_name}' ---"))

        #Create or fetch EvaluationBatch
        batch, created = EvaluationBatch.objects.get_or_create(
            batch_name=batch_name,
            defaults={
                'admin': admin_user,
                'status': 'Processing'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created EvaluationBatch record (Admin: {admin_user.username})"))
        else:
            self.stdout.write(self.style.NOTICE(f"Using existing EvaluationBatch record (Status: {batch.status})"))

        self.stdout.write(f"Processing {len(pdf_files)} submission(s)...")

        for pdf_path in pdf_files:
            self._process_single_pdf(pdf_path, batch)

        #Update batch status to 'Ready' once extraction is complete
        batch.status = 'Ready'
        batch.save()
        self.stdout.write(self.style.SUCCESS(f"Batch '{batch.batch_name}' status updated to 'Ready'.\n"))

    def _process_single_pdf(self, pdf_path: Path, batch: EvaluationBatch):
        #Parsing filename: <enrolmentno>-<coursecode>-<year>.pdf
        enrollment_no, course_code = self._parse_filename(pdf_path.name)

        if not enrollment_no or not course_code:
            self.stderr.write(
                self.style.WARNING(f"Skipping '{pdf_path.name}': filename must follow 'enrolmentno-coursecode-year.pdf' format.")
            )
            return

        #Validate that the Course exists in the database
        course_obj = Course.objects.filter(course_code=course_code).first()

        if not course_obj:
            self.stderr.write(
                self.style.ERROR(
                    f"Course '{course_code}' does not exist in the database. "
                    f"Skipping submission: '{pdf_path.name}'."
                )
            )
            return

        #Extracting text via PyMuPDF and pymupdf4llm
        doc = pymupdf.open(pdf_path)
        full_text = ""
        full_text = pymupdf4llm.to_markdown(doc)
        doc.close()

        #Isolate response body from cover headers
        cleaned_text = self._isolate_answer_body(full_text)

        #Store relative file path from project root
        try:
            stored_relative_path = str(pdf_path.relative_to(settings.BASE_DIR))
        except ValueError:
            stored_relative_path = str(pdf_path)

        #Create or update AssignmentSubmission
        submission, created = AssignmentSubmission.objects.update_or_create(
            batch=batch,
            enrollment_number=enrollment_no,
            course=course_obj,
            defaults={
                'file_path': stored_relative_path,
                'extracted_text': cleaned_text,
                'status': 'Pending Review',
                'evaluator': None
            }
        )

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"  [{action}] Enrollment: {enrollment_no} | Course: {course_code} | Path: {stored_relative_path}"
            )
        )

    def _resolve_admin_user(self, username_filter: str = None):
        """Resolves the Admin user instance for the batch."""
        if username_filter:
            return User.objects.filter(username=username_filter, role='Admin').first()
        return User.objects.filter(role='Admin').first() or User.objects.filter(is_superuser=True).first()

    def _parse_filename(self, filename: str):
        """Parses '<enrolmentno>-<coursecode>-<year>.pdf'
        Example: '2400000001-BCS052-2025-26.pdf' -> ('2400000001', 'BCS052')
        """
        stem = Path(filename).stem
        parts = stem.split('-')

        if len(parts) >= 2:
            enrollment_no = parts[0].strip()
            raw_course = parts[1].strip()
            normalized_course = self._normalize_course_code(raw_course)
            return enrollment_no, normalized_course

        return None, None

    def _normalize_course_code(self, code_str: str) -> str:
        """Strips punctuation/spaces and returns uppercase course code."""
        return re.sub(r'[^A-Za-z0-9]', '', code_str).upper()

    def _isolate_answer_body(self, full_text: str) -> str:
        """Slices text starting from Question 1 where the student writes it before Answer 1,
        skipping the front matter and attached question paper.
        """
        # Matches: 'Q1' / 'Question 1' followed within ~300 chars by an 'Answer' / 'Ans' tag
        pattern = r'(?i)(\b(?:Q\s*1|Question\s*1)\b[\s\S]{1,300}?\b(?:Ans(?:wer)?\b))'
        
        match = re.search(pattern, full_text)
        if match:
            # Start slice at the beginning of the matched 'Question 1'
            content = full_text[match.start():]
        else:
            # Fallback: slice at the first 'Answer' marker if Question 1 wasn't repeated
            fallback = re.search(r'\b(Ans(?:wer)?\s*[\.:\-]*(?:\s*(?:No\.?|Number)?\s*1)?)\b', full_text, re.IGNORECASE)
            content = full_text[fallback.start():] if fallback else full_text

        return re.sub(r'\n{3,}', '\n\n', content).strip()