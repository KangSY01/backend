from django.http import JsonResponse
from .models import Quiz
from .serializers import *

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.auth
import google.auth.transport.requests

import time # ⇐ 추가
import os
import json
import requests
import random
import boto3
import base64
import uuid
import traceback
import re
from dotenv import load_dotenv

import concurrent.futures
from django import db

load_dotenv()

# --- Gemini 및 Vertex AI 설정 ---
try:
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key: raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")
    genai.configure(api_key=gemini_api_key)
    text_model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Gemini API 설정 오류: {e}")
    text_model = None

# --- 상수 정의 ---
S3_BUCKET_NAME = 'iccas-quiz'
S3_REGION = 'ap-northeast-2'
VERTEX_AI_LOCATION = 'us-central1'
VERTEX_AI_MODEL = 'imagegeneration@006'

"""[1단계 게임용 함수] 주어진 감정에 대한 이야기(JSON)를 생성하는 내부 함수"""
def create_new_quiz_data(user_id):
    """퀴즈 생성의 모든 과정을 담당하는 핵심 로직 (프롬프트 검열 포함)"""
    if not text_model:
        raise Exception("Gemini API가 설정되지 않았습니다.")

    image_prompt = None
    
    # 프롬프트 생성 및 검열을 위한 루프 (최대 3번 재시도)
    for attempt in range(3):
        print(f"--- [INFO] Quiz generation attempt {attempt + 1}/3 for user_id: {user_id} ---")
        emotion_map = { "Happiness": "기쁨", "Sadness": "슬픔", "Anger": "화남", "Surprise": "놀람" }
        chosen_emotion_en = random.choice(list(emotion_map.keys()))
        chosen_emotion_ko = emotion_map[chosen_emotion_en]
        
        story_prompt_templates = {
            "Happiness": "The story must be about **at least two cute animal characters** and describe them having **enormous, joyful smiles**.",
            "Sadness": "The story must be about **at least two cute animal characters** and describe at least one of them **visibly crying, with large tears**.",
            "Anger": "The story must be about **at least two cute animal characters** and describe one character's **face turning bright red with anger**.",
            "Surprise": "The story must be about **at least two cute animal characters** and describe **both** of their **mouths forming a perfect 'O' shape** in astonishment when they see the key object."
        }

        # 2. Gemini 프롬프트 최종 생성 - "두 마리 이상의 동물" 조건을 명확히 전달
        prompt_text = f"""
        You are a creative storyteller for a children's therapeutic app.
        Your task is to create a JSON object for a story about the emotion: **{chosen_emotion_en}**.

        **Requirement 1: The story MUST feature exactly THREE cute animal characters.**
        **Requirement 2: Do NOT give the characters proper names.** Describe them by their species or appearance (e.g., 'a fluffy rabbit', 'a tall giraffe', 'a sleepy cat').
        **Requirement 3: {story_prompt_templates.get(chosen_emotion_en, '')}**

        The JSON object must contain:
        1. "story_text": A story about three cute animal characters.
        2. "answer_en": This must be exactly "{chosen_emotion_en}".
        3. "characters": A list of descriptions for all THREE characters in the story.
        4. "key_object": A key object from the story.
        5. "answer_ko": This must be exactly "{chosen_emotion_ko}".
        6. "options_ko": A list of 4 Korean emotion words, including "{chosen_emotion_ko}".
        """
        

        response = text_model.generate_content([{"role": "user", "parts": [prompt_text]}])
        raw_text = response.text.strip()
        try:
            json_string = raw_text.strip('```json').strip()
            quiz_data = json.loads(json_string)
            if isinstance(quiz_data, list): quiz_data = quiz_data[0]
            if not isinstance(quiz_data, dict): raise Exception("유효한 JSON 객체가 아님")
        except (IndexError, json.JSONDecodeError):
            raise Exception(f"Gemini 응답 파싱 실패: {raw_text}")

        story_text = quiz_data.get('story_text')
        answer_en = quiz_data.get('answer_en')
        characters = quiz_data.get('characters')
        key_object = quiz_data.get('key_object')
        options_ko = quiz_data.get('options_ko')
        answer_ko = quiz_data.get('answer_ko')
        if not all([story_text, answer_en, characters, key_object, options_ko, answer_ko]):
            raise Exception(f"유효한 퀴즈 데이터를 받지 못했습니다: {quiz_data}")

        characters = quiz_data.get('characters')
        if not characters or len(characters) < 3:
            raise Exception(f"Gemini가 3명의 캐릭터를 생성하지 않았습니다: {characters}")

        char1, char2, char3 = characters[0], characters[1], characters[2]
        
        # 이미지 프롬프트 생성 (3마리 캐릭터를 모두 포함하도록 수정)
        image_prompt_templates = {
            "happiness": (
                f"A hyper-expressive cartoon of {char1}, {char2}, and {char3}. "
                f"The most important feature is their enormous, joyful smiles that stretch from ear to ear. "
                f"They are all celebrating together around {key_object}. Style: high-quality vector art for toddlers."
            ),
            "sadness": (
                f"A hyper-expressive cartoon of {char1}, {char2}, and {char3}. "
                f"The most important feature is that {char1} is visibly crying, with huge, comical, streaming tears. "
                f"Nearby, {char2} and {char3} have matching sad, empathetic expressions, looking at a broken {key_object}. "
                f"Style: high-quality vector art for toddlers."
            ),
            "anger": (
                f"A hyper-expressive cartoon of {char1}. "
                f"Its entire face is bright red with anger, and comical puffs of steam are coming out of its ears. "
                f"Nearby, {char2} and {char3} look on with worried expressions. "
                f"Style: high-quality vector art for toddlers."
            ),
            "surprise": (
                f"A hyper-expressive cartoon of {char1}, {char2}, and {char3}. "
                f"The absolute most important feature is that all three characters' mouths are frozen wide open in a perfect 'O' shape of astonishment. "
                f"They are all looking at {key_object}. Style: high-quality vector art for toddlers."
            )
        }
        temp_image_prompt = image_prompt_templates.get(answer_en.lower(), f"Three cute animal characters expressing '{answer_en}'.")

        # 프롬프트 검열
        forbidden_keywords = ['child', 'children', 'kid', 'kids', 'baby', 'babies', 'kill', 'fight', 'blood', 'violence']
        prompt_has_forbidden_word = any(word in temp_image_prompt.lower() for word in forbidden_keywords)

        if not prompt_has_forbidden_word:
            image_prompt = temp_image_prompt
            print("--- [INFO] Prompt validation passed. Proceeding to image generation. ---")
            break
        else:
            print(f"--- [WARNING] Forbidden keyword found in prompt. Retrying... ---\nPrompt: {temp_image_prompt}")
            
    if image_prompt is None:
        raise Exception("안전한 이미지 프롬프트를 생성하는 데 3번 실패했습니다.")

    # Vertex AI 인증 및 API 호출
    time.sleep(random.uniform(0.5, 1.5))

    credentials, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    if not project_id:
        raise Exception("Google Cloud Project ID를 찾을 수 없습니다.")
    
    location = "us-central1"
    api_url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/imagegeneration@006:predict"

    payload = { "instances": [{"prompt": image_prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "1:1"} }
    headers = { "Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json; charset=utf-8" }
    
    print(f"--- [DEBUG] Sending to Vertex AI API ---\n{image_prompt}\n---------------------------------------")
    img_response = requests.post(api_url, json=payload, headers=headers, timeout=60)
    img_response.raise_for_status()
    result = img_response.json()
    if "predictions" not in result or not result.get("predictions"):
        raise ValueError("API가 이미지를 반환하지 않았습니다.")
    base64_image = result["predictions"][0]["bytesBase64Encoded"]

    # S3에 이미지 업로드
    s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'), region_name=S3_REGION)
    image_data = base64.b64decode(base64_image)
    image_filename = f"{user_id}/{uuid.uuid4()}.png"
    s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=image_filename, Body=image_data, ContentType='image/png')
    image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{image_filename}"
    
    # DB에 퀴즈 저장
    new_quiz = Quiz.objects.create(
        quiz_image=image_url,
        correct_answer=answer_ko,
        answer_list=options_ko,
    )
    print(f"--- [INFO] New Quiz created with ID: {new_quiz.quiz_id} for User ID: {user_id} ---")
    return new_quiz

"""[3단계 카드게임용 함수] 주어진 감정에 대한 이야기(JSON)를 생성하는 내부 함수"""
def _generate_story_for_emotion(emotion_en, emotion_ko):
    
    # 이 함수 내용은 이전과 동일합니다.
    story_prompt_templates = {
        "Happiness": "The story must be about **at least two cute animal characters** and describe them having **enormous, joyful smiles**.",
        "Sadness": "The story must be about **at least two cute animal characters** and describe at least one of them **visibly crying, with large tears**.",
        "Anger": "The story must be about **at least two cute animal characters** and describe one character's **face turning bright red with anger**.",
        "Surprise": "The story must be about **at least two cute animal characters** and describe **both** of their **mouths forming a perfect 'O' shape** in astonishment when they see the key object."
    }
    prompt_text = f"""
    You are a creative storyteller for a children's therapeutic app.
    Your task is to create a JSON object for a story about the emotion: **{emotion_en}**.
    **Requirement 1: The story MUST feature exactly THREE cute animal characters.**
    **Requirement 2: Do NOT give the characters proper names.** Describe them by their species or appearance (e.g., 'a fluffy rabbit', 'a tall giraffe', 'a sleepy cat').
    **Requirement 3: {story_prompt_templates.get(emotion_en, '')}**
    The JSON object must contain:
    1. "story_text": A story about three cute animal characters.
    2. "answer_en": This must be exactly "{emotion_en}".
    3. "characters": A list of descriptions for all THREE characters in the story.
    4. "key_object": A key object from the story.
    5. "answer_ko": This must be exactly "{emotion_ko}".
    6. "options_ko": A list of 4 Korean emotion words, including "{emotion_ko}".
    """
    response = text_model.generate_content([{"role": "user", "parts": [prompt_text]}])
    raw_text = response.text.strip()
    try:
        json_string = raw_text.strip('```json').strip()
        quiz_data = json.loads(json_string)
        if isinstance(quiz_data, list): quiz_data = quiz_data[0]
        if not all(k in quiz_data for k in ['story_text', 'answer_en', 'characters', 'key_object', 'options_ko', 'answer_ko']):
            raise ValueError("Required keys are missing from the JSON response.")
        return quiz_data
    except (json.JSONDecodeError, ValueError) as e:
        print(f"이야기 생성 또는 파싱 실패 (감정: {emotion_en}): {e}\nRaw Text: {raw_text}")
        return None

"""[3단계 카드게임용 함수] 이야기 데이터로 이미지를 생성하고 DB에 퀴즈를 저장하는 함수 (지수 백오프 적용)"""
def _create_image_and_quiz(user_id, story_data):
    
    if not story_data:
        raise ValueError("이미지를 생성할 이야기 데이터가 없습니다.")
    
    # 이야기 데이터로부터 이미지 프롬프트 생성
    answer_en = story_data['answer_en']
    char1, char2, char3 = story_data['characters'][0], story_data['characters'][1], story_data['characters'][2]
    key_object = story_data['key_object']

    image_prompt_templates = {
        "happiness": f"A hyper-expressive cartoon of {char1}, {char2}, and {char3}. The most important feature is their enormous, joyful smiles. They are all celebrating together around {key_object}. Style: high-quality vector art for toddlers.",
        "sadness": f"A hyper-expressive cartoon of {char1}, {char2}, and {char3}. The most important feature is that {char1} is visibly crying, with huge, comical, streaming tears. Nearby, {char2} and {char3} have matching sad expressions, looking at a broken {key_object}. Style: high-quality vector art for toddlers.",
        "anger": f"A hyper-expressive cartoon of {char1}. Its entire face is bright red with anger, and comical puffs of steam are coming out of its ears. Nearby, {char2} and {char3} look on with worried expressions. Style: high-quality vector art for toddlers.",
        "surprise": f"A hyper-expressive cartoon of {char1}, {char2}, and {char3}. The absolute most important feature is that all three characters' mouths are frozen wide open in a perfect 'O' shape of astonishment. They are all looking at {key_object}. Style: high-quality vector art for toddlers."
    }
    image_prompt = image_prompt_templates.get(
        answer_en.lower(), 
        f"A cartoon of {char1}, {char2}, and {char3} expressing the emotion of {answer_en}. Style: high-quality vector art for toddlers."
    )

    # Google Cloud 인증 정보 준비
    credentials, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    auth_req = google.auth.transport.requests.Request()
    
    # 재시도 로직을 위한 변수 설정
    max_retries = 3
    base_delay = 1  # 초 단위

    # 최대 3번까지 API 호출 재시도
    for attempt in range(max_retries):
        try:
            # 매 시도마다 토큰을 갱신하여 만료 문제 방지
            credentials.refresh(auth_req)
            
            # API 요청 정보 설정
            location = "us-central1"
            api_url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/imagegeneration@006:predict"
            payload = {"instances": [{"prompt": image_prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}}
            headers = {"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json; charset=utf-8"}
            
            # 이미지 생성 API 호출
            img_response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            
            # 4xx, 5xx 에러 발생 시 예외를 발생시킴
            img_response.raise_for_status() 

            result = img_response.json()

            # 응답에 'predictions' 키가 있는지 확인
            if "predictions" in result and result.get("predictions"):
                # 성공 시, base64 이미지 데이터 추출
                base64_image = result["predictions"][0]["bytesBase64Encoded"]
                
                # S3에 이미지 업로드
                s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'), region_name=S3_REGION)
                image_data = base64.b64decode(base64_image)
                image_filename = f"{user_id}/{uuid.uuid4()}.png"
                s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=image_filename, Body=image_data, ContentType='image/png')
                image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{image_filename}"
                
                # DB에 퀴즈 저장
                new_quiz = Quiz.objects.create(
                    quiz_image=image_url,
                    correct_answer=story_data['answer_ko'],
                    answer_list=story_data['options_ko'],
                )
                print(f"--- [SUCCESS] Image created for emotion '{story_data['answer_en']}' on attempt {attempt + 1} ---")
                return new_quiz
            else:
                # 성공(200 OK) 응답이지만 prediction이 없는 경우 (안전 필터 등)
                print(f"--- [WARNING] No predictions found, attempt {attempt + 1}/{max_retries}. Response: {result} ---")
                return None

        except requests.exceptions.HTTPError as e:
            # 429 에러인 경우에만 재시도
            if e.response.status_code == 429:
                if attempt < max_retries - 1:
                    # 대기 시간을 2배씩 늘려가며 재시도 (1초, 2초, 4초...)
                    wait_time = base_delay * (2 ** attempt)
                    print(f"--- [RATE LIMIT] 429 Too Many Requests. Retrying in {wait_time} seconds... ---")
                    time.sleep(wait_time)
                else:
                    # 모든 재시도를 소진한 경우
                    print(f"--- [FATAL] Exceeded max retries for 429 error. ---")
                    return None
            else:
                # 429가 아닌 다른 HTTP 에러는 즉시 예외를 발생시킴
                print(f"--- [HTTP ERROR] An unhandled HTTP error occurred: {e} ---")
                raise e # 혹은 return None 처리
        except Exception as e:
            # 기타 다른 에러 발생 시
            print(f"--- [ERROR] An unexpected error occurred: {e} ---")
            return None

    # 모든 재시도 후에도 성공하지 못한 경우
    return None

""" [3단계 카드게임용 함수] 하나의 감정에 대해 2개의 퀴즈(카드) 쌍을 생성하는 작업 함수 이미지 생성 실패 시, 새로운 이야기로 최대 3번까지 재시도합니다."""
def create_quiz_pair(user_id, emotion_tuple):
    emotion_en, emotion_ko = emotion_tuple
    try:
        for attempt in range(3):
            print(f"--- [PAIR ATTEMPT {attempt + 1}/3] Generating story for '{emotion_en}' ---")
            
            # 1. 새로운 이야기와 프롬프트를 생성합니다.
            story_data = _generate_story_for_emotion(emotion_en, emotion_ko)
            if not story_data:
                print(f"--- [WARNING] Story generation failed for '{emotion_en}'. Retrying... ---")
                time.sleep(1) # 잠시 대기 후 재시도
                continue

            # 2. 첫 번째 이미지 생성 시도
            quiz1 = _create_image_and_quiz(user_id, story_data)
            if not quiz1:
                print(f"--- [WARNING] First image creation failed for '{emotion_en}'. Retrying with new story... ---")
                time.sleep(1)
                continue

            # 3. 두 번째 이미지 생성 시도
            quiz2 = _create_image_and_quiz(user_id, story_data)
            if not quiz2:
                print(f"--- [WARNING] Second image creation failed for '{emotion_en}'. Retrying with new story... ---")
                time.sleep(1)
                continue

            # 4. 두 이미지 모두 성공적으로 생성되면, 결과를 반환하고 루프를 종료합니다.
            print(f"--- [SUCCESS] Successfully created a pair for '{emotion_en}' ---")
            return [quiz1, quiz2]

        # 3번의 시도 모두 실패한 경우
        print(f"--- [FATAL] Failed to create a pair for '{emotion_en}' after 3 attempts. ---")
        return []

    finally:
        db.connection.close()

# ==============================================================================
#  API 뷰(Views)
# ==============================================================================

class QuizListView(APIView):
    """ GET: 모든 퀴즈 목록을 보여줍니다. """
    def get(self, request):
        quizzes = Quiz.objects.all().order_by('-created_at')
        serializer = QuizSerializer(quizzes, many=True)
        return Response(serializer.data)

""" POST: [1단계] 5개의 무작위 퀴즈를 생성합니다. """
class QuizCreateView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        if user_id is None:
            return Response({'error': 'user_id가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                results = executor.map(create_new_quiz_data, [user_id] * 5)
                new_quizzes = list(q for q in results if q is not None)
            serializer = QuizSerializer(new_quizzes, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(traceback.format_exc())
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            db.connections.close_all()

""" POST: [3단계 카드게임] 4쌍의 카드 게임용 퀴즈 (총 8개)를 생성합니다. """
class CardGameCreateView(APIView):
    
    def post(self, request):
        user_id = request.data.get('user_id')
        if user_id is None:
            return Response({'error': 'user_id가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # ▼▼▼ 'Fear'를 제외한 4개의 기본 감정만 사용합니다. ▼▼▼
            emotion_map = { "Happiness": "기쁨", "Sadness": "슬픔", "Anger": "화남", "Surprise": "놀람" }
            
            # ▼▼▼ 5개가 아닌 4개의 감정을 선택하도록 수정합니다. ▼▼▼
            if len(emotion_map) < 4:
                 raise ValueError("퀴즈를 생성하려면 최소 4개의 감정이 필요합니다.")
            
            selected_emotions = random.sample(list(emotion_map.items()), 4)
            print(f"--- [CARD GAME INFO] Selected emotions: {[emo[0] for emo in selected_emotions]} ---")
            
            # ▼▼▼ 병렬 작업자 수를 4개로 맞춰줍니다. (선택사항이지만 효율적) ▼▼▼
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                quiz_pairs_futures = [executor.submit(create_quiz_pair, user_id, emo) for emo in selected_emotions]
                
                final_quiz_list = []
                for future in concurrent.futures.as_completed(quiz_pairs_futures):
                    final_quiz_list.extend(future.result())

            serializer = QuizSerializer(final_quiz_list, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(traceback.format_exc())
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            db.connections.close_all()


class ThirdGameResultSaveView(APIView):
    """
    하나의 카드 게임 결과를 받아 DB에 저장하는 API
    """
    def post(self, request):
        # request.data가 단일 객체이므로 many=True 옵션을 제거합니다.
        serializer = ThirdGameResultSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': '게임 결과가 성공적으로 저장되었습니다.'},
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
