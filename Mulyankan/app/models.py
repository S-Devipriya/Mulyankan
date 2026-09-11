from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from pgvector.django import VectorField

# 1.Custom User Model for Role-Based Access Control
class User(AbstractUser):
    ROLE_CHOICES = (
        ('Admin', 'Admin'),
        ('Evaluator', 'Evaluator'),
        ('User', 'User'),
    )
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='User')

    REQUIRED_FIELDS = ['email', 'role']

    def __str__(self):
        return f"{self.username} ({self.role})"


# 2.Course Model
class Course(models.Model):
    course_code = models.CharField(max_length=20, unique=True)
    course_name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.course_code} - {self.course_name}"


# 3.Evaluator Expertise Mapping
class EvaluatorExpertise(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'Evaluator'})
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'course')
        verbose_name_plural = "Evaluator Expertise"

    def __str__(self):
        return f"{self.user.username} -> {self.course.course_code}"


# 4.Course Context for Textbook Chunks & Embeddings
class CourseContext(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    text_chunk = models.TextField()
    page_number = models.IntegerField()
    block_number = models.IntegerField()
    unit_number = models.IntegerField()
    embedding = VectorField(dimensions=384)

    def __str__(self):
        return f"{self.course.course_code} [P.{self.page_number} / U.{self.unit_number}]"


# 5.Evaluation Batch
class EvaluationBatch(models.Model):
    STATUS_CHOICES = (
        ('Processing', 'Processing'),
        ('Ready', 'Ready'),
        ('Completed', 'Completed'),
    )
    batch_name = models.CharField(max_length=100)
    admin = models.ForeignKey(User, on_delete=models.PROTECT, limit_choices_to={'role': 'Admin'})
    upload_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Processing')

    class Meta:
        verbose_name_plural = "Evaluation Batches"

    def __str__(self):
        return f"{self.batch_name} ({self.status})"


# 6.Assignment Submission
class AssignmentSubmission(models.Model):
    STATUS_CHOICES = (
        ('Pending Review', 'Pending Review'),
        ('Reviewed', 'Reviewed'),
    )
    batch = models.ForeignKey(EvaluationBatch, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    evaluator = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        limit_choices_to={'role': 'Evaluator'}
    )
    enrollment_number = models.CharField(max_length=20)
    extracted_text = models.TextField()
    file_path = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending Review')

    def __str__(self):
        return f"{self.enrollment_number} - {self.course.course_code}"


# 7.Evaluation Result
class EvaluationResult(models.Model):
    submission = models.OneToOneField(AssignmentSubmission, on_delete=models.CASCADE, related_name='evaluation_result')
    score_content = models.DecimalField(max_digits=5, decimal_places=2)
    score_linguistic = models.DecimalField(max_digits=5, decimal_places=2)
    score_presentation = models.DecimalField(max_digits=5, decimal_places=2)
    suggested_final_score = models.DecimalField(max_digits=5, decimal_places=2)
    human_final_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    plagiarism_percentage = models.IntegerField(default=0)
    ai_percentage = models.IntegerField(default=0)
    evaluator_remarks = models.TextField(null=True, blank=True)
    audit_logic = models.JSONField(help_text="Stores array of citations, source pairings, and context chunks")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Result: {self.submission.enrollment_number} (Score: {self.human_final_score})"