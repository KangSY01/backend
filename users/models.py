from django.db import models

class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    age = models.IntegerField(null=True, blank=True)
    point = models.IntegerField(null=True, blank=True)
    base_character_name = models.CharField(max_length=50, null=True, blank=True)
    base_character_img = models.TextField(null=True, blank=True)
    base_background_name = models.CharField(max_length=50, null=True, blank=True)
    base_background_img = models.JSONField(null=True, blank=True)
    store_character = models.JSONField(null=True, blank=True)
    store_background = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users'  # 테이블명 명시
