from rest_framework import serializers
from .models import User

class UserSignupSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(required=True, error_messages={
        'required': 'Age is required.',
        'invalid': 'Age must be a valid number.'
    })

    class Meta:
        model = User
        fields = '__all__'
        read_only_fields = ['user_id']

    def validate_username(self, value):
        if not value.strip():
            raise serializers.ValidationError("Username cannot be empty.")
        return value

    def validate_password(self, value):
        if not value.strip():
            raise serializers.ValidationError("Password cannot be empty.")
        return value

    def create(self, validated_data):
        # 자동으로 기본 캐릭터 및 배경 값 세팅
        validated_data['base_character_name'] = 'cat'
        validated_data['base_character_img'] = 'https://iccas-zerodose.s3.ap-northeast-2.amazonaws.com/character/cat/cat_main.png'
        validated_data['base_background_name'] = 'yard'
        validated_data['base_background_img'] = [
            "https://iccas-zerodose.s3.ap-northeast-2.amazonaws.com/background/yard/set/yard1.jpg",
            "https://iccas-zerodose.s3.ap-northeast-2.amazonaws.com/background/yard/set/yard2.png",
            "https://iccas-zerodose.s3.ap-northeast-2.amazonaws.com/background/yard/set/yard3.jpg"
        ]

        return User.objects.create(**validated_data)


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'