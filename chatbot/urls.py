from django.urls import path
from . import views

urlpatterns = [
    # Existing URLs
    path('', views.chat_home, name='chat_home'),
    path('api/', views.chat_api, name='chat_api'),
    path('learn/', views.learning_hub, name='learning_hub'),
    path('learn/<int:resource_id>/', views.resource_detail, name='resource_detail'),
    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('quizzes/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('quizzes/<int:quiz_id>/take/', views.quiz_take, name='quiz_take'),
    
    # --- NEW: Authentication URLs ---
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
]