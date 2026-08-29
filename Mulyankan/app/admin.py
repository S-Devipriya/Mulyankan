from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, Course, EvaluatorExpertise, CourseContext, 
    EvaluationBatch, AssignmentSubmission, EvaluationResult
)

class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role', 'is_staff', 'is_active']
    list_filter = ['role', 'is_staff', 'is_active']

# Register your models here.
admin.site.register(User, CustomUserAdmin)
admin.site.register(Course)
admin.site.register(EvaluatorExpertise)
admin.site.register(CourseContext)
admin.site.register(EvaluationBatch)
admin.site.register(AssignmentSubmission)
admin.site.register(EvaluationResult)