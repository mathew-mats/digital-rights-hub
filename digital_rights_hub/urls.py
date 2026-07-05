from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static

urlpatterns = [
    # Admin panel at /admin/
    path('admin/', admin.site.urls),
    
    # All chatbot URLs (defined in chatbot/urls.py) will be at the root
    # For example, /api/ will be handled by chatbot.views.chat_api
    path('', include('chatbot.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
