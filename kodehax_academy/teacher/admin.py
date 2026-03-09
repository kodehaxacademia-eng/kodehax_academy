from django.contrib import admin
from .models import (
    Assignment,
    ClassRoom,
    CodeSubmission,
    QuizAnswer,
    QuizResult,
    QuizQuestion,
    Submission,
    TeacherProfile,
)

admin.site.register(ClassRoom)
admin.site.register(Assignment)
admin.site.register(Submission)
admin.site.register(QuizQuestion)
admin.site.register(QuizAnswer)
admin.site.register(QuizResult)
admin.site.register(CodeSubmission)
admin.site.register(TeacherProfile)
