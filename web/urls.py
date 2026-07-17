from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('chat/init/', views.chat_init, name='chat_init'),
    path('chat/send/', views.chat_send, name='chat_send'),
]