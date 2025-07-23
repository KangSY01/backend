from django.db import models
from django.utils import timezone

class Quiz(models.Model):
    quiz_id = models.AutoField(primary_key=True)
    quiz_image = models.TextField(blank=True, null=True)
    correct_answer = models.CharField(max_length=255, blank=True, null=True)
    answer_list = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'quiz'