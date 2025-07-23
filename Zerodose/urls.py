from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/quiz/', include('quiz.urls')),
    path('api/data/', include('data.urls')),
    path('api/item/', include('item.urls')),  # 이 줄 추가
]
