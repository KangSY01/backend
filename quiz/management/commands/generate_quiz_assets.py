from django.core.management.base import BaseCommand
import random
import time
import json
import re
import traceback
import uuid
import os
import google.auth                 # ⇐ 이 줄을 추가하세요.
import google.auth.transport.requests # ⇐ 이 줄을 추가하세요.
import boto3
import google.generativeai as genai
import requests
from dotenv import load_dotenv
import base64 # ⇐ 이 줄을 추가하세요.
# --- 기본 설정 ---
load_dotenv()
try:
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")
    genai.configure(api_key=gemini_api_key)
    text_model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Gemini API 설정 오류: {e}")
    text_model = None

# --- S3 및 템플릿 정보 ---
S3_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'iccas-quiz')
S3_REGION = os.environ.get('AWS_S3_REGION_NAME', 'ap-northeast-2')

QUIZ_TEMPLATES = [
    {
        "id": "swing_turn",
        "prompts": {
            "situation": {
                "positive": "A playground with one empty swing. The first character and the second character stand nearby, looking at the swing with EXCITED faces.",
                "negative": "sitting on the swing, only one character"
            },
            "correct": {
                "positive": "A happy scene. The first character is on the swing, SMILING. The second character is behind, pushing the swing and also SMILING.",
                "negative": "sad, angry, fighting, only one character"
            },
            "incorrect": {
                # ▼▼▼ 여기가 다시 수정된 부분입니다 ▼▼▼
                "positive": "The main subject of the image is a single playground swing. In the foreground, standing directly IN FRONT OF the swing, are the first character and the second character. They are facing each other, arguing about the swing. Both characters have VERY ANGRY expressions with furrowed brows.",
                # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
                "negative": "smiling, happy, playing, touching the swing, sitting on the swing, calm"
            }
        }
    },
    {
        "id": "blocks_knocked_over",
        "prompts": {
            "situation": {
                "positive": "A tall block tower has fallen over. The second character is on the floor CRYING with big tears. The first character, who knocked it over, looks SHOCKED with a wide-open mouth.",
                "negative": "smiling, happy, laughing, only one character"
            },
            "correct": {
                "positive": "The first character has a SORRY expression and is helping the second character rebuild the block tower. The second character is now SMILING.",
                "negative": "angry, fighting, arguing, only one character"
            },
            "incorrect": {
                # ▼▼▼ 여기가 최종 수정된 부분입니다 ▼▼▼
                "positive": "An emotionally divided scene. CRITICAL: The two characters MUST have OPPOSITE emotions. The setting is a floor with fallen blocks. The second character ('the victim') is in the foreground, sitting next to the blocks and CRYING with big tears. The first character ('the offender') is in the background, actively running away from the victim, and has a mischievous SMILING face. Do not show empathy.",
                # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
                "negative": "helping, happy victim, sad offender, crying offender, both characters crying, same emotion on both characters"
            }
        }
    },
    {
        "id": "share_toy",
        "prompts": {
            "situation": {
                "positive": "The first character is holding a shiny, colorful robot toy with blinking eyes and wheels. The robot is clearly active and fun-looking. The second character sits nearby with both hands empty, leaning forward slightly, eyes fixed on the toy with visible interest.",
                "negative": "no toy, both characters smiling together, looking elsewhere, holding hands"
            },
            "correct": {
                "positive": "The first character gently offers the robot toy to the second character with a warm smile. The second character takes it with both hands and beams with joy. Now they are sitting together and playing cooperatively.",
                "negative": "still alone, holding toy tightly, ignoring each other, no interaction"
            },
            "incorrect": {
                "positive": "The first character grips the robot tightly in both arms and turns away protectively. The second character sits with visibly empty hands in their lap, looking down sadly. The distance between them is emphasized.",
                "negative": "smiling together, playing together, toy between them, sharing happily"
            }
        }
    },
    {
        "id": "say_sorry",
        "prompts": {
            "situation": {
                "positive": "Two characters are walking directly toward each other and collide at the center of the scene. The first character’s arms have just hit the second character’s shoulder, and the second character is falling backward onto the ground. Their eyes are wide with shock. The impact is clear, and their body language shows surprise and imbalance.",
                "negative": "no collision, walking side-by-side, holding hands, smiling or laughing"
            },
            "correct": {
                "positive": "The first character stands with a slightly hunched posture, head bowed in apology. The second character remains sitting on the ground, looking up. The first character's hands are together in front or slightly out, clearly expressing a sorry gesture. Their facial expressions show sincerity and emotional connection.",
                "negative": "both standing, no apology pose, smiling, ignoring, both on ground"
            },
            "incorrect": {
                "positive": "The second character is still sitting on the ground, crying with their head buried in their arms. The first character has turned around and is walking away into the distance, clearly facing away. The physical gap is wide, and there is no eye contact. The emotion is cold and disconnected.",
                "negative": "helping hand offered, looking back, standing close, interacting"
            }
        }
    },
    {
        "id": "respond_to_greeting",
        "prompts": {
            "situation": {
                "positive": "Two characters are standing face-to-face on a bright outdoor sidewalk in front of a school building. The first character is smiling and waving with their right hand. The second character is standing still and looking at the first character with a neutral expression. Their feet are about one step apart. The sunlight creates soft shadows.",
                "negative": "hugging, angry face, walking away, no waving, sitting, indoors, third character"
            },
            "correct": {
                "positive": "Both characters are smiling and waving at each other with one hand. Their faces are friendly and bright. The posture of both characters is open and welcoming, standing face-to-face.",
                "negative": "ignoring, turning away, sad expressions, no waving, angry, walking apart"
            },
            "incorrect": {
                "positive": "The first character is smiling and waving with one hand. The second character has an angry face and is physically pushing or shoving the first character. The mood is tense and confrontational. The first character looks surprised or sad.",
                "negative": "waving back, smiling together, peaceful scene, friendly interaction, standing calmly"
            }
        }
    },
    {
        "id": "quiet_in_library",
        "prompts": {
            "situation": {
                "positive": "The first and second characters are seated at a wooden library table. Each has an open book in front of them. They are quietly reading with their heads slightly bowed and calm facial expressions. Bookshelves fill the background, and the room has a peaceful, quiet atmosphere.",
                "negative": "talking loudly, standing up, no books, toys on table, laughter, running"
            },
            "correct": {
                "positive": "The second character is softly whispering to the first character while pointing at a page in their book. Both characters are seated and focused, with relaxed postures and gentle expressions, showing respectful behavior in the quiet library.",
                "negative": "wide open mouths, shouting, laughter, standing, no books, third character present"
            },
            "incorrect": {
                "positive": "The first character is standing on their chair and shouting with their mouth wide open. The second character looks surprised or uncomfortable. A few books have fallen onto the floor, disrupting the quiet library atmosphere.",
                "negative": "both seated, reading calmly, whispering, soft lighting, peaceful, third character"
            }
        }
    },
    {
        "id": "thank_you",
        "prompts": {
            "situation": {
                "positive": "The first character is holding out a large chocolate chip cookie with both hands, offering it to the second character. The second character is facing the first character with wide eyes, showing surprise. They are standing in a neutral, indoor setting like a classroom or playroom.",
                "negative": "no cookie, already smiling, hugging, sitting, ignoring, blurry hands"
            },
            "correct": {
                "positive": "The second character receives the cookie with both hands while smiling brightly. The first character is also smiling. Their eye contact shows positive connection. The moment is warm, friendly, and peaceful.",
                "negative": "angry faces, no cookie, walking away, sad expressions, dropped cookie"
            },
            "incorrect": {
                "positive": "The second character looks very angry and throws the cookie on the floor. The first character looks shocked or hurt. The cookie is mid-air or on the ground. The atmosphere is clearly negative and emotionally tense.",
                "negative": "smiling, saying thank you, receiving cookie, holding it gently, eye contact"
            }
        }
    },
    {
        "id": "help_carry_items",
        "prompts": {
            "situation": {
                "positive": "In a bright indoor hallway, the second character is struggling to carry a tall stack of books and toys. Their arms are full, and the items look unstable. The first character is nearby, watching with a neutral expression, standing with empty hands. Both characters are in casual clothes appropriate for school or daycare.",
                "negative": "helping, no items, only one character, happy, smiling together, standing side-by-side"
            },
            "correct": {
                "positive": "The first character is reaching out with both hands to help the second character carry the tall stack of books and toys. The second character looks visibly relieved and is smiling. The hallway is bright, and both characters appear engaged in helping.",
                "negative": "one character, ignoring, struggling alone, dropping items, sad, angry expressions"
            },
            "incorrect": {
                "positive": "The first character is walking away with their hands in their pockets or playing with a toy, clearly ignoring the second character who is still struggling with the heavy stack. The second character’s face shows clear discomfort or frustration.",
                "negative": "helping hand, standing close, smiling at each other, cooperative posture, making eye contact"
            }
        }
    },
    {
        "id": "clean_up_after_play",
        "prompts": {
            "situation": {
                "positive": "A playroom scene with many colorful toys scattered on the floor—blocks, stuffed animals, and toy cars. The first and second characters are sitting or kneeling among the toys. They are looking at the mess with calm or thoughtful expressions, preparing to clean up together. Storage bins and shelves are visible in the background.",
                "negative": "cleaned room, empty floor, toys already in bins, only one character, playing, not looking at toys"
            },
            "correct": {
                "positive": "Both the first and second characters are cleaning up toys together. One is picking up toy blocks and placing them in a plastic storage bin, while the other is gathering stuffed animals from the floor. Their facial expressions are positive—focused or slightly smiling. The room still has some scattered toys, showing active cleanup.",
                "negative": "toys still everywhere, only one character cleaning, ignoring toys, fighting, sad or angry expressions"
            },
            "incorrect": {
                "positive": "The second character is walking away from the messy floor with their hands in their pockets. The first character is cleaning up alone, looking tired or disappointed. Toys are still scattered everywhere, and the second character shows no interest in helping.",
                "negative": "helping, smiling together, both characters cleaning, no toys left on the floor, teamwork, cooperative posture"
            }
        }
    },
    {
        "id": "react_to_accident",
        "prompts": {
            "situation": {
                "positive": "The first character accidentally spills a cup of water onto the second character’s clothes. The spill is visible on the second character’s shirt or pants. The first character looks surprised and a little worried. The setting is a classroom or indoor playroom with bright lighting.",
                "negative": "already angry, dry clothes, food spill, only one character, smiling, laughing"
            },
            "correct": {
                "positive": "The second character calmly picks up a nearby towel or tissue and gently wipes the spilled water off their clothes. Their face looks composed, with no sign of anger. The first character is still standing nearby, looking relieved or thankful. The mood is calm and cooperative.",
                "negative": "angry face, shouting, splashing, walking away, hands up, blaming gestures"
            },
            "incorrect": {
                "positive": "The second character jumps up and yells at the first character, pointing at their wet clothes with an angry expression. The first character looks scared or confused. The scene is tense, and there is no sign of resolution.",
                "negative": "smiling, wiping calmly, friendly posture, relaxed, helping behavior"
            }
        }
    },
]

def _validate_image_with_prompt(prompt, image_data_bytes):
    try:
        validator_prompt = f"You are a precise image QA expert. Does the given IMAGE accurately depict ALL key elements from the given TEXT PROMPT? TEXT PROMPT: \"{prompt}\". Respond ONLY with a valid JSON object: {{\"is_match\": boolean, \"reason\": \"brief explanation in Korean\"}}"
        image_part = {"mime_type": "image/png", "data": image_data_bytes}
        response = text_model.generate_content([validator_prompt, image_part], request_options={'timeout': 60})
        raw_text = response.text
        match = re.search(r'\{[\s\S]*\}', raw_text)
        if not match: return False, f"유효하지 않은 검증 응답: {raw_text}"
        result_json = json.loads(match.group(0))
        return result_json.get("is_match", False), result_json.get("reason", "No reason provided.")
    except Exception as e:
        return False, f"검증 중 에러 발생: {e}"

def _generate_and_upload_one_image(prompt, s3_key_prefix, negative_prompt=None):
    try:
        credentials, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        location = "us-central1"
        api_url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/imagegeneration@006:predict"
        payload = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}}
        if negative_prompt:
            payload["parameters"]["negativePrompt"] = negative_prompt
        headers = {"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json; charset=utf-8"}
        img_response = requests.post(api_url, json=payload, headers=headers, timeout=120)
        img_response.raise_for_status()
        result = img_response.json()
        if "predictions" in result and result.get("predictions"):
            base64_image = result["predictions"][0]["bytesBase64Encoded"]
            image_data_bytes = base64.b64decode(base64_image)
            is_valid, reason = _validate_image_with_prompt(prompt, image_data_bytes)
            if is_valid:
                s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'), region_name=S3_REGION)
                image_filename = f"{s3_key_prefix}{uuid.uuid4()}.png"
                s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=image_filename, Body=image_data_bytes, ContentType='image/png')
                return f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{image_filename}", reason
            else:
                return None, reason
        else:
            return None, f"API 응답에 prediction 없음: {result}"
    except Exception as e:
        return None, f"이미지 생성 중 에러 발생: {e}"

CHARACTER_PAIRS = [
    ["a cute fluffy bunny", "a kind brown bear"],
    ["a playful puppy with floppy ears", "a tiny kitten with big blue eyes"],
    ["a clever orange fox with a bushy tail", "a curious little squirrel"],
    ["a sleepy panda cub", "a brave little lion cub"],
    ["a baby penguin with fluffy gray feathers and tiny orange feet", 
 "a gentle white lamb with soft wool and big round eyes"],
]


# --- Django 관리 명령어 클래스 ---
class Command(BaseCommand):
    help = 'Generates and uploads validated quiz image assets to S3.'

    def add_arguments(self, parser):
        """명령어 실행 시 받을 인자(argument)를 정의합니다."""
        parser.add_argument('template_id', type=str, help='The ID of the quiz template (e.g., swing_turn).')
        parser.add_argument(
            'category', 
            type=str, 
            help="The category to generate images for ('situation', 'correct', 'incorrect', or 'all')."
        )
        parser.add_argument('count', type=int, help='The number of images to generate per category.')

    def _run_generation_for_category(self, category_name, prompts_data, count, template_id):
        """특정 카테고리에 대한 이미지 생성 루프를 실행하는 헬퍼 메서드"""
        self.stdout.write(f"\n--- Generating {count} images for category: {category_name} ---")
        s3_prefix = f"social_quiz/{template_id}/{category_name}/"
        successful_uploads = 0
        total_attempts = 0

        while successful_uploads < count:
            total_attempts += 1
            self.stdout.write(f"  Attempting to create image #{successful_uploads + 1} (Total tries: {total_attempts})...")
            
            # 미리 정의된 리스트에서 캐릭터를 무작위로 선택
            char1_desc, char2_desc = random.choice(CHARACTER_PAIRS)
            self.stdout.write(f"    -> Selected Characters: {char1_desc}, {char2_desc}")

            art_style = "Style: hyper-expressive and cute cartoon for toddlers, high-quality vector art, soft and friendly colors, simple background."
            character_definition = f"The first character is {char1_desc}. The second character is {char2_desc}."
            
            positive_prompt = f"{character_definition} {prompts_data['positive']} {art_style}"
            negative_prompt = prompts_data.get('negative')
            
            # 이미지 생성, 검증, 업로드 시도
            image_url, reason = _generate_and_upload_one_image(positive_prompt, s3_prefix, negative_prompt)
            
            if image_url:
                successful_uploads += 1
                self.stdout.write(self.style.SUCCESS(f"    -> Success! Image #{successful_uploads} saved to S3."))
            else:
                self.stdout.write(self.style.WARNING(f"    -> Failed. Reason: {reason}. Retrying..."))
        
        self.stdout.write(self.style.SUCCESS(f"--- Finished for category: {category_name} ---"))

    def handle(self, *args, **options):
        """명령어가 실행될 때 호출되는 메인 메서드"""
        template_id = options['template_id']
        category_to_generate = options['category']
        count = options['count']

        if not text_model:
            self.stderr.write(self.style.ERROR("Gemini API not configured."))
            return

        self.stdout.write(self.style.SUCCESS(f"Starting asset generation for template '{template_id}'..."))
        template = next((t for t in QUIZ_TEMPLATES if t['id'] == template_id), None)
        if not template:
            self.stderr.write(self.style.ERROR(f"Template '{template_id}' not found."))
            return

        # 'all' 인 경우, 모든 카테고리에 대해 생성
        if category_to_generate.lower() == 'all':
            for category, prompts_data in template['prompts'].items():
                self._run_generation_for_category(category, prompts_data, count, template_id)
        # 특정 카테고리가 지정된 경우
        else:
            prompts_data = template['prompts'].get(category_to_generate)
            if prompts_data:
                self._run_generation_for_category(category_to_generate, prompts_data, count, template_id)
            else:
                self.stderr.write(self.style.ERROR(f"Category '{category_to_generate}' not found in template '{template_id}'. "
                                                    f"Available categories are: {list(template['prompts'].keys())} or 'all'."))
                return

        self.stdout.write(self.style.SUCCESS("\nAll requested tasks completed!"))