from rest_framework import serializers
from .models import Item
from users.models import User

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = '__all__'

class AddItemToUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    item_name = serializers.CharField()
    item_type = serializers.IntegerField()

    def validate(self, data):
        user_id = data['user_id']
        item_name = data['item_name']
        item_type = data['item_type']

        try:
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("해당 유저가 존재하지 않습니다.")

        if item_type == 1:
            if user.store_character and item_name in user.store_character:
                raise serializers.ValidationError("해당 캐릭터 아이템은 이미 보유하고 있습니다.")
        elif item_type == 2:
            if user.store_background and item_name in user.store_background:
                raise serializers.ValidationError("해당 배경 아이템은 이미 보유하고 있습니다.")
        else:
            raise serializers.ValidationError("item_type은 1(캐릭터) 또는 2(배경)만 가능합니다.")

        return data

    def create(self, validated_data):
        user = User.objects.get(user_id=validated_data['user_id'])
        item_name = validated_data['item_name']
        item_type = validated_data['item_type']

        if item_type == 1:
            user.store_character = (user.store_character or []) + [item_name]
        elif item_type == 2:
            user.store_background = (user.store_background or []) + [item_name]

        user.save()
        return user
    

class UpdateBaseSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    item_name = serializers.CharField()

    def validate(self, data):
        user_id = data['user_id']
        item_name = data['item_name']

        try:
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("해당 유저가 존재하지 않습니다.")

        store_characters = user.store_character or []
        store_backgrounds = user.store_background or []

        if item_name not in store_characters and item_name not in store_backgrounds:
            raise serializers.ValidationError("item_name이 유저의 보유 아이템에 존재하지 않습니다.")

        data['user_instance'] = user  # 이후에 활용하기 위해 저장
        data['is_character'] = (item_name in store_characters)
        data['is_background'] = (item_name in store_backgrounds)

        return data