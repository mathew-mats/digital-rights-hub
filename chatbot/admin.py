from django.contrib import admin
from .models import (
    FAQ, ChatSession, ChatMessage, Resource,
    Quiz, QuizQuestion, QuizAttempt, QuizResponse, Profile,
)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_avatar_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email')
    
    def get_avatar_preview(self, obj):
        if obj.avatar:
            return f'<img src="{obj.avatar.url}" width="50" height="50" style="border-radius:50%;" />'
        return 'No avatar'
    get_avatar_preview.allow_tags = True
    get_avatar_preview.short_description = 'Avatar'

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'created_at')
    search_fields = ('question', 'answer')
    list_filter = ('category',)

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'user', 'created_at', 'is_active')
    list_filter = ('is_active',)

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'message', 'is_bot', 'created_at')
    list_filter = ('is_bot',)

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'resource_type', 'is_published', 'created_at')
    list_filter = ('category', 'resource_type', 'is_published')
    search_fields = ('title', 'summary', 'content')

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'difficulty', 'is_published', 'created_at')
    list_filter = ('category', 'difficulty', 'is_published')
    search_fields = ('title', 'description')

@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'question_text', 'correct_answer', 'order')
    list_filter = ('quiz',)
    search_fields = ('question_text',)

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'user', 'score', 'total_questions', 'passed', 'completed_at')
    list_filter = ('quiz', 'passed')

@admin.register(QuizResponse)
class QuizResponseAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'selected_answer', 'is_correct')
    list_filter = ('is_correct',)