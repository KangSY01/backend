from django.urls import path
from .views import *

urlpatterns = [
    path('all/', ItemListView.as_view()),
    path('buy/', AddItemToUserView.as_view()),
    path('base-setting/', UpdateBaseView.as_view()),
]