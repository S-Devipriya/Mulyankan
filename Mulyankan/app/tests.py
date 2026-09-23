from django.test import TestCase
import csv
from io import StringIO
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from app.services.plagiarism_checker import compute_peer_similarity, compute_textbook_overlap
from app.models import Course, EvaluationBatch, AssignmentSubmission, EvaluationResult, EvaluatorExpertise

# Create your tests here.

User = get_user_model()

class MulyankanTestCase(TestCase):

    def setUp(self):
        #creates Users for each role
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Password123!',
            role='Admin'
        )
        self.evaluator_user = User.objects.create_user(
            username='evaluator_test',
            email='evaluator@test.com',
            password='Password123!',
            role='Evaluator'
        )
        self.standard_user = User.objects.create_user(
            username='student_test',
            email='student@test.com',
            password='Password123!',
            role='User'
        )

        #creates Course and Expertise
        self.course = Course.objects.create(
            course_code='BCS052',
            course_name='Network Programming'
        )
        EvaluatorExpertise.objects.create(
            user=self.evaluator_user,
            course=self.course
        )

        #creates an Evaluation Batch
        self.batch = EvaluationBatch.objects.create(
            batch_name='BCAOL-Jan2026Intake-2026-27',
            admin=self.admin_user,
            status='Ready'
        )

        #creates an Assignment Submissions
        self.submission_1 = AssignmentSubmission.objects.create(
            batch=self.batch,
            course=self.course,
            evaluator=self.evaluator_user,
            enrollment_number='2400000001',
            extracted_text='Sample answer text for question 1',
            file_path='data/sample_submissions/2400000001-BCS052-2026-27.pdf',
            status='Pending Review'
        )
        self.submission_2 = AssignmentSubmission.objects.create(
            batch=self.batch,
            course=self.course,
            evaluator=self.evaluator_user,
            enrollment_number='2400000002',
            extracted_text='Sample answer text for question 2',
            file_path='data/sample_submissions/2400000002-BCS052-2026-27.pdf',
            status='Pending Review'
        )

        #creates Evaluation Results with mock audit_logic
        self.mock_audit_logic = [
            {'question': 'Q1', 'max_marks': 15.0, 'citation': 'Unit 1 Page 4'},
            {'question': 'Q2', 'max_marks': 15.0, 'citation': 'Unit 2 Page 12'}
        ]

        self.result_1 = EvaluationResult.objects.create(
            submission=self.submission_1,
            score_content=12.0,
            score_linguistic=4.0,
            score_presentation=4.0,
            suggested_final_score=20.0,
            audit_logic=self.mock_audit_logic
        )
        self.result_2 = EvaluationResult.objects.create(
            submission=self.submission_2,
            score_content=10.0,
            score_linguistic=3.5,
            score_presentation=3.5,
            suggested_final_score=17.0,
            audit_logic=self.mock_audit_logic
        )

        #Client instance
        self.client = Client()

    # UT-01: Model Integrity & Relationships
    def test_model_creations_and_string_representations(self):
        #Verify model instances create cleanly and string methods work.
        self.assertEqual(str(self.admin_user), 'admin_test (Admin)')
        self.assertEqual(str(self.course), 'BCS052 - Network Programming')
        self.assertEqual(str(self.batch), 'BCAOL-Jan2026Intake-2026-27 (Ready)')
        self.assertEqual(str(self.submission_1), '2400000001 - BCS052')
        self.assertEqual(self.submission_1.status, 'Pending Review')
        self.assertEqual(self.submission_1.evaluation_result.suggested_final_score, 20.0)

    # UT-02: Role-Based Access Control (RBAC) & View Decorators
    def test_unauthenticated_user_redirects_to_login(self):
        response = self.client.get(reverse('admin_dashboard'))
        self.assertRedirects(response, reverse('login'))

        response = self.client.get(reverse('evaluator_dashboard'))
        self.assertRedirects(response, reverse('login'))

    def test_rbac_admin_dashboard_permissions(self):
        #Normal User can't access admin dashboard
        self.client.login(username='student_test', password='Password123!')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 403)

        #Evaluator User also can't access admin dashboard (403 PermissionDenied)
        self.client.login(username='evaluator_test', password='Password123!')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 403)

        #Admin User can access admin dashboard (200 Success)
        self.client.login(username='admin_test', password='Password123!')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_rbac_evaluator_dashboard_permissions(self):
        #Normal User can't access evaluator dashboard
        self.client.login(username='student_test', password='Password123!')
        response = self.client.get(reverse('evaluator_dashboard'))
        self.assertEqual(response.status_code, 403)
        
        #Evaluators can access evaluator dashboard
        self.client.login(username='evaluator_test', password='Password123!')
        response = self.client.get(reverse('evaluator_dashboard'))
        self.assertEqual(response.status_code, 200)

    # UT-03: Profile View
    def test_profile_page_access(self):
        self.client.login(username='evaluator_test', password='Password123!')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'evaluator_test')
        self.assertContains(response, 'BCS052')

    # UT-04: Human-in-the-Loop (HITL) Score Override & Batch Progression
    def test_human_evaluation_override_and_batch_completion(self):
        self.client.login(username='evaluator_test', password='Password123!')

        #Evaluating Submission 1 (Total max marks = 30.0)
        url_1 = reverse('evaluate_submission', kwargs={'submission_id': self.submission_1.id})
        post_data_1 = {
            'human_final_score': '22.50',
            'evaluator_remarks': 'Good explanation of concept.'
        }
        response_1 = self.client.post(url_1, post_data_1)
        
        #Reloading submission_1 from DB
        self.submission_1.refresh_from_db()
        self.result_1.refresh_from_db()
        
        self.assertEqual(self.submission_1.status, 'Reviewed')
        self.assertEqual(self.result_1.human_final_score, 22.50)
        self.assertEqual(self.result_1.evaluator_remarks, 'Good explanation of concept.')
        self.assertIsNotNone(self.result_1.reviewed_at)

        #Batch should still be 'Ready' because submission_2 is still 'Pending Review'
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, 'Ready')

        #Evaluating Submission 2 (Last pending submission in batch)
        url_2 = reverse('evaluate_submission', kwargs={'submission_id': self.submission_2.id})
        post_data_2 = {
            'human_final_score': '25.00',
            'evaluator_remarks': 'Excellent diagrammatic presentation.'
        }
        response_2 = self.client.post(url_2, post_data_2)

        #Reloading submission_2 and batch from DB
        self.submission_2.refresh_from_db()
        self.batch.refresh_from_db()

        self.assertEqual(self.submission_2.status, 'Reviewed')
        #All submissions reviewed so Batch status must automatically transition to 'Completed'
        self.assertEqual(self.batch.status, 'Completed')

    # UT-05: Score Validation Bounds
    def test_invalid_score_override_rejection(self):
        self.client.login(username='evaluator_test', password='Password123!')
        url = reverse('evaluate_submission', kwargs={'submission_id': self.submission_1.id})
        
        #Max marks for mock audit logic is 30.0; submitting invalid 50.0
        post_data = {
            'human_final_score': '50.00',
            'evaluator_remarks': 'Out of bounds score'
        }
        response = self.client.post(url, post_data)
        
        self.submission_1.refresh_from_db()
        self.assertNotEqual(self.submission_1.status, 'Reviewed')
        self.assertIsNone(self.submission_1.evaluation_result.human_final_score)

    # UT-06: CSV Results Export
    def test_csv_export_endpoint(self):
        self.client.login(username='admin_test', password='Password123!')
        response = self.client.get(reverse('export_results_csv'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="mulyankan_results_all.csv"', response['Content-Disposition'])

        #Parsing CSV output stream
        csv_content = response.content.decode('utf-8')
        csv_reader = list(csv.reader(StringIO(csv_content)))
        
        #Verifying Headers
        self.assertEqual(csv_reader[0], ['Enrollment Number', 'Course Code', 'Batch Name', 'Evaluator', 'Final Score'])
        
        #Collecting extracted enrollment numbers across data rows
        extracted_enrollments = [row[0] for row in csv_reader[1:]]
        self.assertIn('2400000001', extracted_enrollments)
        self.assertIn('2400000002', extracted_enrollments)

class PlagiarismCheckerTestCase(TestCase):
    # UT-07: Peer Plagiarism Computation for similar student responses
    def test_compute_peer_similarity_high_overlap(self):
        text_a = "Dijkstra algorithm finds the shortest path in a weighted graph with non negative edge weights."
        text_b = "Dijkstra algorithm is used to find the shortest path in a weighted graph with non negative edge weights."

        score = compute_peer_similarity(text_a, text_b, n=4)
        self.assertGreaterEqual(score, 50.0)

    # UT-08: Peer Plagiarism Computation for dissimilar student responses
    def test_compute_peer_similarity_low_overlap(self):
        text_a = "Python standard libraries provide built in data structures like lists and dictionaries."
        text_b = "Computer networking operates on OSI layers including physical data link transport and application."

        score = compute_peer_similarity(text_a, text_b, n=4)
        self.assertLess(score, 20.0)

    # UT-09: Textbook Context Similarity Matching
    def test_compute_textbook_overlap_matching_chunks(self):
        student_answer = "Relational database management systems use SQL to execute queries and manage data in normalized tables."
        context_chunks = [
            {"text_chunk": "Relational database management systems use SQL queries to fetch data from normalized tables."},
            {"text_chunk": "Normalized tables prevent redundancy in relational systems."}
        ]

        overlap_score = compute_textbook_overlap(student_answer, context_chunks, n=4)
        self.assertGreater(overlap_score, 0.0)