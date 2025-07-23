from django.db import models

class Item(models.Model):
    item_id = models.AutoField(primary_key=True)
    item_type = models.IntegerField()
    item_name = models.CharField(max_length=255)
    item_img = models.TextField()
    item_detail_img = models.JSONField()
    price = models.IntegerField()
    
    class Meta:
        db_table = 'item'  # <- MySQL에 수동으로 만든 테이블 이름
