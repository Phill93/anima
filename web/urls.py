from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('chat/init/', views.chat_init, name='chat_init'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path('manage/', views.manage, name='manage'),
    path('manage/session/<int:session_id>/', views.view_session, name='view_session'),
    path('manage/get_char/', views.get_character_data, name='get_character_data'),
    path('manage/get_memories/', views.get_character_memories, name='get_character_memories'),
    path('manage/mem/delete/', views.delete_memory, name='delete_memory'),
    path('manage/global/get/', views.get_global_settings, name='get_global_settings'),
    path('manage/global/save/', views.save_global_settings, name='save_global_settings'),
    path('manage/char/save/', views.save_character, name='save_character'),
    path('manage/trait/save/', views.save_trait, name='save_trait'),
    path('manage/trait/delete/', views.delete_trait, name='delete_trait'),
]