from django.test import TestCase

# Create your tests here.
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zerodose.settings')

django.setup()

from main.models import User, Quiz, GameLog

user, _ = User.objects.get_or_create(username="테스트유저", age=10, point=0)
quiz, _ = Quiz.objects.get_or_create(
    quiz_image="img1.png",
    quiz_answer="기쁨",
    quiz_list=["기쁨", "슬픔", "분노"]
)

GameLog.objects.create(user=user, quiz=quiz, selected="기쁨", is_correct=True, response_time=2.5)
GameLog.objects.create(user=user, quiz=quiz, selected="슬픔", is_correct=False, response_time=3.1)

print("테스트 데이터 삽입 완료!")
