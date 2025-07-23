from rest_framework import serializers
from .models import Quiz
from data.models import QuizResult  # data 앱에 있는 QuizResult 모델을 가져옵니다.

class QuizSerializer(serializers.ModelSerializer):
    """
    퀴즈 데이터를 보여주기 위한 Serializer
    """
    class Meta:
        model = Quiz
        fields = '__all__' # 모델의 모든 필드를 포함

class QuizCreateSerializer(serializers.Serializer):
    """
    퀴즈 생성을 위해 user_id를 입력받기 위한 Serializer
    """
    user_id = serializers.IntegerField()

class QuizAnswerSerializer(serializers.Serializer):
    """
    사용자의 답변(selected)을 입력받기 위한 Serializer
    """
    selected = serializers.CharField(max_length=255)



class ThirdGameResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizResult
        # 프론트엔드에서 보낸 데이터 중, DB에 저장할 필드들을 지정합니다.
        fields = ['user_id', 'quiz_id', 'duration_seconds']

    def create(self, validated_data):
        # 데이터 생성 시, quiz_type을 3 (카드 게임)으로 고정합니다.
        validated_data['quiz_type'] = 3
        return QuizResult.objects.create(**validated_data)