from django.db import models
from django.contrib.auth.models import User
from PIL import Image
import os

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def get_avatar_url(self):
        """Get the avatar URL or return default if not set."""
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return f'https://ui-avatars.com/api/?name={self.user.username}&background=4a9eff&color=fff&size=100'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Resize image if it exists
        if self.avatar and self.avatar.path:
            try:
                img = Image.open(self.avatar.path)
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.avatar.path)
            except Exception:
                pass

# --- FAQ ---
class FAQ(models.Model):
    CATEGORY_CHOICES = [
        ('privacy', 'Data Privacy'),
        ('ai_policy', 'AI Policy'),
        ('cybersecurity', 'Cybersecurity'),
        ('digital_rights', 'Digital Rights'),
        ('internet_governance', 'Internet Governance'),
    ]
    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.question[:50]
    class Meta:
        ordering = ['category', 'question']

# --- ChatSession ---
class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"Session {self.session_id[:8]}"

# --- ChatMessage ---
class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message = models.TextField()
    is_bot = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        sender = 'Bot' if self.is_bot else 'User'
        return f"{sender}: {self.message[:30]}"

# --- Resource ---
class Resource(models.Model):
    RESOURCE_TYPES = [
        ('article', 'Article'),
        ('video', 'Video'),
        ('pdf', 'PDF'),
        ('link', 'External Link'),
    ]
    CATEGORY_CHOICES = [
        ('digital_rights', 'Digital Rights'),
        ('privacy', 'Data Privacy'),
        ('ai_policy', 'AI Policy'),
        ('cybersecurity', 'Cybersecurity'),
        ('internet_governance', 'Internet Governance'),
        ('general', 'General'),
    ]
    title = models.CharField(max_length=200)
    summary = models.TextField()
    content = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='article')
    url = models.URLField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True)
    def __str__(self):
        return self.title
    class Meta:
        ordering = ['-created_at']

# --- Quiz ---
class Quiz(models.Model):
    CATEGORY_CHOICES = [
        ('digital_rights', 'Digital Rights'),
        ('privacy', 'Data Privacy'),
        ('ai_policy', 'AI Policy'),
        ('cybersecurity', 'Cybersecurity'),
        ('internet_governance', 'Internet Governance'),
        ('general', 'General'),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    difficulty = models.CharField(max_length=20, choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ], default='beginner')
    time_limit = models.IntegerField(default=5)
    passing_score = models.IntegerField(default=70)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.title
    def get_question_count(self):
        return self.questions.count()

# --- QuizQuestion ---
class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=300)
    option_b = models.CharField(max_length=300)
    option_c = models.CharField(max_length=300)
    option_d = models.CharField(max_length=300)
    correct_answer = models.CharField(max_length=1, choices=[
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
    ])
    order = models.IntegerField(default=0)
    def __str__(self):
        return f"{self.quiz.title} - Q{self.order + 1}"

# --- QuizAttempt ---
class QuizAttempt(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    session_id = models.CharField(max_length=100, blank=True, null=True)
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-completed_at']
    def __str__(self):
        return f"{self.quiz.title} - {self.score}/{self.total_questions}"

# --- QuizResponse ---
class QuizResponse(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=1, choices=[
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
    ])
    is_correct = models.BooleanField(default=False)
    def __str__(self):
        return f"{self.question.question_text[:30]} - {'Correct' if self.is_correct else 'Wrong'}"

# Admin model

class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_super_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Admin: {self.user.username}"