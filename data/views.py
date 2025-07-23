from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import QuizResultSerializer

class QuizResultCreateView(APIView):
    def post(self, request):
        serializer = QuizResultSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from collections import defaultdict
from .models import QuizResult

class EmotionStatView(APIView):
    def post(self, request):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"error": "user_id is required"}, status=400)

        logs = QuizResult.objects.filter(user_id=user_id)
        if not logs.exists():
            return Response({"message": "No data found."}, status=200)

        emotion_data = defaultdict(lambda: {"attempts": 0, "correct": 0})
        for log in logs:
            emotion = log.emotion or log.quiz.quiz_answer
            emotion_data[emotion]["attempts"] += 1
            if log.is_correct:
                emotion_data[emotion]["correct"] += 1

        result = {}
        for emotion, data in emotion_data.items():
            attempts = data["attempts"]
            correct = data["correct"]
            result[emotion] = {
                "attempts": attempts,
                "correct": correct,
                "rate": round(correct / attempts, 2) if attempts else 0.0
            }

        return Response(result)


class LearningCurveView(APIView):
    def post(self, request):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"error": "user_id is required"}, status=400)

        logs = QuizResult.objects.filter(user_id=user_id).order_by('created_at')

        curve = defaultdict(list)
        for log in logs:
            emotion = log.emotion or log.quiz.quiz_answer
            curve[emotion].append(1 if log.is_correct else 0)

        result = {}
        for emotion, records in curve.items():
            running_total = 0
            progression = []
            for i, v in enumerate(records):
                running_total += v
                progression.append(round(running_total / (i + 1), 2))
            result[emotion] = progression

        return Response(result)
