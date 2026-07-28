from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views


urlpatterns = [
    # Admin panel at /admin/
    path('admin/', admin.site.urls),
    path('captcha/', include('captcha.urls')),

    # ===== PASSWORD RESET =====
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='chatbot/password_reset.html',
             email_template_name='chatbot/password_reset_email.html',
             subject_template_name='chatbot/password_reset_subject.txt'
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='chatbot/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='chatbot/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='chatbot/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    
    # All chatbot URLs (defined in chatbot/urls.py) will be at the root
    # For example, /api/ will be handled by chatbot.views.chat_api
    path('', include('chatbot.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
