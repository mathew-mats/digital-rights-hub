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
    path('profile/edit/', views.edit_profile, name='edit_profile'),  # <-- ADD THIS
    path('profile/delete-avatar/', views.delete_avatar, name='delete_avatar'),  
    # Admin URLs
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-resources/', views.admin_resources, name='admin_resources'),
    path('admin-resources/delete/<int:resource_id>/', views.admin_delete_resource, name='admin_delete_resource'),
    path('admin-quizzes/', views.admin_quizzes, name='admin_quizzes'),
    path('admin-quizzes/<int:quiz_id>/', views.admin_quiz_detail, name='admin_quiz_detail'),
    path('admin-quizzes/delete/<int:quiz_id>/', views.admin_delete_quiz, name='admin_delete_quiz'),
    path('admin-questions/delete/<int:question_id>/', views.admin_delete_question, name='admin_delete_question'),
    path('admin-faqs/', views.admin_faqs, name='admin_faqs'),
    path('admin-faqs/delete/<int:faq_id>/', views.admin_delete_faq, name='admin_delete_faq'),
    path('admin-users/', views.admin_users, name='admin_users'),  # <-- ADD THIS
    path('admin-users/toggle/<int:user_id>/', views.admin_toggle_user_status, name='admin_toggle_user_status'),
    path('admin-users/delete/<int:user_id>/', views.admin_delete_user, name='admin_delete_user'),
]