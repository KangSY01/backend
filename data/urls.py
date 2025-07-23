from django.urls import path
from .views import QuizResultCreateView, EmotionStatView, LearningCurveView

urlpatterns = [
    path('quiz_result/', QuizResultCreateView.as_view(), name='quiz_result_create'),
    path('api/data/emotion/', EmotionStatView.as_view()),
    path('api/data/curve/', LearningCurveView.as_view()),
]
