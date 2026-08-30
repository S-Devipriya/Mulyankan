import os
import re
from pathlib import Path
import pymupdf
import json
from sentence_transformers import SentenceTransformer
from django.core.management.base import BaseCommand
from django.conf import settings
from app.models import Course, CourseContext


class Command(BaseCommand):
    help = 'Ingests SLM textbook PDFs, chunks text, generates embeddings, and saves to pgvector.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course',
            type=str,
            help='Specify a single course code to ingest (e.g. BCS052 or ECO01). If omitted, ingests all found.'
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=400,
            help='Target number of words per text chunk (default: 400).'
        )
        parser.add_argument(
            '--chunk-overlap',
            type=int,
            default=50,
            help='Number of overlapping words between chunks (default: 50).'
        )

    def handle(self, *args, **options):
        course_filter = options.get('course')
        chunk_size = options.get('chunk_size')
        chunk_overlap = options.get('chunk_overlap')

        # data/ folder resides at root project level
        data_dir = settings.BASE_DIR / 'data' / 'textbooks'

        if not data_dir.exists():
            self.stderr.write(self.style.ERROR(f"Textbook directory not found at: {data_dir}"))
            return

        self.stdout.write(self.style.NOTICE("Loading embedding model (all-MiniLM-L6-v2)..."))
        model = SentenceTransformer('all-MiniLM-L6-v2')

        manifest_path = data_dir / 'courses.json'
        course_manifest = {}

        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    course_manifest = json.load(f)
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"Failed to read courses.json: {e}"))    

        # Search for course folders
        course_folders = [f for f in data_dir.iterdir() if f.is_dir()]
        if course_filter:
            course_folders = [f for f in course_folders if f.name.upper() == course_filter.upper()]

        if not course_folders:
            self.stderr.write(self.style.WARNING(f"No matching course directories found in {data_dir}"))
            return

        for course_folder in course_folders:
            course_code = course_folder.name.strip()
            self.stdout.write(self.style.HTTP_INFO(f"\nProcessing Course: {course_code}"))

            course_meta = course_manifest.get(course_code, {})
            # Fallback hierarchy: JSON course_name -> folder name (course_code)
            course_title = course_meta.get('course_name') or course_code

            # Ensure Course exists in DB
            course_obj, created = Course.objects.get_or_create(
                course_code=course_code,
                defaults={'course_name': course_title}
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created new Course entry: {course_code}"))

            if not created and course_title != course_code and course_obj.course_name != course_title:
                course_obj.course_name = course_title
                course_obj.save(update_fields=['course_name'])

            pdf_files = list(course_folder.glob('**/*.pdf'))
            if not pdf_files:
                self.stdout.write(self.style.WARNING(f"No PDF files found inside {course_folder}"))
                continue

            total_chunks_created = 0

            for pdf_path in pdf_files:
                # Extract Block and Unit numbers from directory/filename patterns
                block_num = self._extract_number(pdf_path.parent.name, default=1)
                unit_num = self._extract_number(pdf_path.stem, default=1)

                self.stdout.write(f" -> Ingesting: {pdf_path.name} (Block {block_num}, Unit {unit_num})")

                doc = pymupdf.open(pdf_path)
                for page_idx in range(len(doc)):
                    page_num = page_idx + 1
                    page = doc.load_page(page_idx)
                    text = page.get_text("text").strip()

                    if not text or len(text) < 40:
                        continue  # Skip blank pages / headers only

                    # Create overlapping chunks
                    chunks = self._chunk_text(text, chunk_size, chunk_overlap)

                    for chunk_text in chunks:
                        # Compute 384-dimensional vector embedding
                        embedding_vector = model.encode(chunk_text).tolist()

                        # Save to PostgreSQL CourseContext
                        CourseContext.objects.create(
                            course=course_obj,
                            text_chunk=chunk_text,
                            page_number=page_num,
                            block_number=block_num,
                            unit_number=unit_num,
                            embedding=embedding_vector
                        )
                        total_chunks_created += 1

                doc.close()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Finished {course_code}: Created and stored {total_chunks_created} vector chunks."
                )
            )

    def _extract_number(self, text, default=1):
        """Extracts first integer found in string (e.g. 'Unit-2.pdf' -> 2, 'Block_1' -> 1)."""
        match = re.search(r'\d+', text)
        return int(match.group()) if match else default

    def _chunk_text(self, text, chunk_size, chunk_overlap):
        """Splits text into chunks of `chunk_size` words with `chunk_overlap` words overlap."""
        words = text.split()
        if len(words) <= chunk_size:
            return [" ".join(words)]

        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start += chunk_size - chunk_overlap
        return chunks