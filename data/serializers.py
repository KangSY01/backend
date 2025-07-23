from rest_framework import serializers
from .models import QuizResult

class QuizResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizResult
        fields = ['result_id', 'user_id', 'quiz_id', 'selected', 'is_correct', 'duration_seconds', 'emotion', 'created_at']
        read_only_fields = ['result_id', 'created_at']
