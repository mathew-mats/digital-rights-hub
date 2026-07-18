from django.contrib.auth import login, authenticate, logout
from django.contrib.messages import get_messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db.models import Q
from django.contrib import messages
import json
import uuid
import re
import traceback

from .models import FAQ, ChatSession, ChatMessage, Resource, Quiz, QuizQuestion, QuizAttempt, QuizResponse, Profile

# --- NO GEMINI CLIENT AT STARTUP! ---
# Gemini will be loaded ONLY when needed in the function below

MODEL_NAME = 'gemini-2.0-flash'
MAX_HISTORY = 10

# --- Synonym dictionary for fallback ---
SYNONYMS = {
    'privacy': ['private', 'personal data', 'data protection', 'confidential'],
    'rights': ['right', 'entitlement', 'freedom', 'legal'],
    'cyber': ['online', 'internet', 'digital', 'web'],
    'security': ['safe', 'protection', 'secure', 'safety'],
    'law': ['act', 'regulation', 'policy', 'legislation', 'statute'],
    'ai': ['artificial intelligence', 'machine learning', 'ml', 'intelligent'],
    'governance': ['govern', 'management', 'administration', 'igf'],
    'uganda': ['ugandan', 'ug', 'local'],
}

# ---------- CHATBOT WITH MEMORY ----------

def get_conversation_history(session):
    """Get last N messages from session."""
    messages = ChatMessage.objects.filter(session=session).order_by('-created_at')[:MAX_HISTORY]
    history = []
    for msg in reversed(messages):
        role = 'user' if not msg.is_bot else 'assistant'
        history.append({'role': role, 'content': msg.message})
    return history

def get_faq_fallback(user_message):
    """Fallback FAQ matching."""
    clean_msg = re.sub(r'[^\w\s]', '', user_message.lower())
    user_words = set(clean_msg.split())
    expanded_words = set(user_words)
    for word in user_words:
        for key, synonyms in SYNONYMS.items():
            if word == key or word in synonyms:
                expanded_words.add(key)
                expanded_words.update(synonyms)

    all_faqs = FAQ.objects.all()
    best_match = None
    best_score = 0
    for faq in all_faqs:
        faq_words = set(faq.question.lower().split())
        matches = len(expanded_words.intersection(faq_words))
        if user_message.lower() in faq.question.lower():
            matches += 5
        if matches > best_score:
            best_score = matches
            best_match = faq
    if best_match and best_score >= 2:
        return best_match.answer
    return ("I don't have a specific answer for that. "
            "Please explore our Learning Resources or contact the Uganda Youth Internet Governance Forum (UYIGF).")

def get_gemini_response_with_memory(user_message, history):
    """Smart hybrid: FAQ first, Gemini fallback (lazy loaded)."""
    # STEP 1: CHECK FAQ DATABASE FIRST
    faq_answer = get_faq_fallback(user_message)
    if faq_answer and "I don't have a specific answer" not in faq_answer:
        return faq_answer

    # STEP 2: NO FAQ MATCH - TRY GEMINI (Lazy load)
    try:
        # --- Lazy load Gemini ONLY when needed ---
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Build the prompt
        history_text = ""
        for entry in history:
            role = "User" if entry['role'] == 'user' else "Assistant"
            history_text += f"{role}: {entry['content']}\n"
        
        prompt = f"""
You are a digital rights assistant for Uganda called "Digital Rights Navigator".

Your purpose:
- Provide comprehensive, detailed, and educational answers about digital rights, internet governance, AI policy, data privacy, and cybersecurity in Uganda.
- Your answers should be well-structured, include examples, legal references (like the Data Protection Act), and practical advice.
- Keep responses detailed but clear (150-250 words).
- Write in paragraphs with proper spacing for readability.

IMPORTANT RULES:
- ONLY answer questions about digital rights, internet governance, AI policy, data privacy, and cybersecurity in Uganda.
- For questions about politics, sports, entertainment, or general knowledge, politely say: "I'm sorry, I'm only trained to answer questions about digital rights, internet governance, AI policy, data privacy, and cybersecurity in Uganda. Please ask me about those topics!"
- Always mention Ugandan context (laws, institutions like NITA-U, UCC, CERT-UG, etc.).
- Use line breaks between paragraphs for readability.

Conversation history:
{history_text}

User: {user_message}

Assistant:"""
        
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        raw_response = response.text
        formatted_response = raw_response.replace('\n\n', '<br><br>').replace('\n', '<br>')
        return formatted_response
        
    except Exception as e:
        print(f"Gemini error: {e}")
        return ("I'm currently having trouble connecting to my AI service. "
                "Please check our Learning Hub for resources on "
                "digital rights, AI policy, and cybersecurity in Uganda!")

@csrf_exempt
def chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            session_id = data.get('session_id')
            if not user_message:
                return JsonResponse({'error': 'Empty message'}, status=400)

            if session_id:
                session, created = ChatSession.objects.get_or_create(session_id=session_id)
            else:
                session = ChatSession.objects.create(session_id=str(uuid.uuid4()))

            ChatMessage.objects.create(session=session, message=user_message, is_bot=False)

            history = get_conversation_history(session)
            bot_response = get_gemini_response_with_memory(user_message, history)

            ChatMessage.objects.create(session=session, message=bot_response, is_bot=True)

            return JsonResponse({
                'response': bot_response,
                'session_id': session.session_id
            })

        except Exception as e:
            return JsonResponse({
                'error': 'I\'m having trouble connecting. Please try again in a moment.'
            }, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

def chat_home(request):
    return render(request, 'chatbot/index.html')

# ---------- LEARNING HUB ----------

def learning_hub(request):
    category = request.GET.get('category', '')
    search = request.GET.get('search', '')
    resource_type = request.GET.get('type', '')
    resources = Resource.objects.filter(is_published=True)
    if category:
        resources = resources.filter(category=category)
    if resource_type:
        resources = resources.filter(resource_type=resource_type)
    if search:
        resources = resources.filter(
            Q(title__icontains=search) |
            Q(summary__icontains=search) |
            Q(content__icontains=search)
        )
    categories = Resource.CATEGORY_CHOICES
    context = {
        'resources': resources,
        'categories': categories,
        'current_category': category,
        'current_type': resource_type,
        'search_query': search,
    }
    return render(request, 'chatbot/learning_hub.html', context)

def resource_detail(request, resource_id):
    try:
        resource = Resource.objects.get(id=resource_id, is_published=True)
        return render(request, 'chatbot/resource_detail.html', {'resource': resource})
    except Resource.DoesNotExist:
        return render(request, 'chatbot/404.html', status=404)

# ---------- QUIZ VIEWS ----------

def quiz_list(request):
    category = request.GET.get('category', '')
    difficulty = request.GET.get('difficulty', '')
    quizzes = Quiz.objects.filter(is_published=True)
    if category:
        quizzes = quizzes.filter(category=category)
    if difficulty:
        quizzes = quizzes.filter(difficulty=difficulty)
    categories = Quiz.CATEGORY_CHOICES
    difficulties = Quiz._meta.get_field('difficulty').choices
    context = {
        'quizzes': quizzes,
        'categories': categories,
        'difficulties': difficulties,
        'current_category': category,
        'current_difficulty': difficulty,
    }
    return render(request, 'chatbot/quiz_list.html', context)

def quiz_detail(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, is_published=True)
    questions = quiz.questions.all().order_by('order')
    user = request.user if request.user.is_authenticated else None
    previous_attempts = QuizAttempt.objects.filter(
        quiz=quiz,
        user=user
    ) if user else QuizAttempt.objects.filter(
        quiz=quiz,
        session_id=request.session.session_key
    )
    best_score = previous_attempts.order_by('-score').first() if previous_attempts.exists() else None
    context = {
        'quiz': quiz,
        'questions': questions,
        'question_count': questions.count(),
        'previous_attempts': previous_attempts.count(),
        'best_score': best_score,
    }
    return render(request, 'chatbot/quiz_detail.html', context)

def quiz_take(request, quiz_id):
    try:
        quiz = get_object_or_404(Quiz, id=quiz_id, is_published=True)
        questions = quiz.questions.all().order_by('order')
        if request.method == 'POST':
            score = 0
            total = questions.count()
            if total == 0:
                return HttpResponse("No questions in this quiz.", status=400)
            
            # --- FIX: Ensure session exists ---
            if not request.session.session_key:
                request.session.create()
            
            user = request.user if request.user.is_authenticated else None
            session_id = request.session.session_key if not user else ''
            
            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                user=user,
                session_id=session_id,
                score=0,
                total_questions=total,
                passed=False
            )
            # ... rest of the function
            for question in questions:
                answer_key = f'question_{question.id}'
                user_answer = request.POST.get(answer_key)
                is_correct = (user_answer == question.correct_answer)
                if is_correct:
                    score += 1
                QuizResponse.objects.create(
                    attempt=attempt,
                    question=question,
                    selected_answer=user_answer or '',
                    is_correct=is_correct
                )
            passed = (score / total * 100) >= quiz.passing_score
            attempt.score = score
            attempt.passed = passed
            attempt.save()
            responses = QuizResponse.objects.filter(attempt=attempt).select_related('question')
            context = {
                'quiz': quiz,
                'attempt': attempt,
                'score': score,
                'total': total,
                'percentage': int(score / total * 100),
                'passed': passed,
                'responses': responses,
            }
            return render(request, 'chatbot/quiz_result.html', context)
        context = {
            'quiz': quiz,
            'questions': questions,
            'question_count': questions.count(),
        }
        return render(request, 'chatbot/quiz_take.html', context)
    except Exception as e:
        return HttpResponseServerError(f"Error: {e}\n{traceback.format_exc()}")

# ---------- AUTHENTICATION VIEWS ----------

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'chatbot/register.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return render(request, 'chatbot/register.html')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'chatbot/register.html')
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.save()
        login(request, user)
        messages.success(request, f'Welcome, {username}!')
        return redirect('profile')
    return render(request, 'chatbot/register.html')

def user_login(request):
    if request.user.is_authenticated:
        return redirect('profile')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {username}!')
            return redirect('profile')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'chatbot/login.html')

def user_logout(request):
    storage = get_messages(request)
    for _ in storage:
        pass
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('chat_home')

@login_required
def profile(request):
    user = request.user
    quiz_attempts = QuizAttempt.objects.filter(user=user).select_related('quiz')
    total_quizzes = quiz_attempts.count()
    passed_quizzes = quiz_attempts.filter(passed=True).count()
    total_score = sum(attempt.score for attempt in quiz_attempts)
    avg_score = (total_score / total_quizzes) if total_quizzes > 0 else 0
    context = {
        'user': user,
        'quiz_attempts': quiz_attempts,
        'total_quizzes': total_quizzes,
        'passed_quizzes': passed_quizzes,
        'avg_score': avg_score,
    }
    return render(request, 'chatbot/profile.html', context)

# ---------- ADMIN DASHBOARD VIEWS ----------
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404

def admin_login(request):
    """Admin login page."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Invalid credentials or not an admin.')
    
    return render(request, 'chatbot/admin_login.html')

@staff_member_required
def admin_dashboard(request):
    """Admin dashboard with stats."""
    context = {
        'total_resources': Resource.objects.count(),
        'total_quizzes': Quiz.objects.count(),
        'total_users': User.objects.count(),
        'total_faqs': FAQ.objects.count(),
        'recent_resources': Resource.objects.order_by('-created_at')[:5],
        'recent_users': User.objects.order_by('-date_joined')[:5],
    }
    return render(request, 'chatbot/admin_dashboard.html', context)

@staff_member_required
def admin_resources(request):
    """Manage resources."""
    resources = Resource.objects.all().order_by('-created_at')
    if request.method == 'POST':
        # Add new resource
        title = request.POST.get('title')
        summary = request.POST.get('summary')
        content = request.POST.get('content')
        category = request.POST.get('category')
        resource_type = request.POST.get('resource_type')
        url = request.POST.get('url')
        
        Resource.objects.create(
            title=title,
            summary=summary,
            content=content,
            category=category,
            resource_type=resource_type,
            url=url,
            is_published=True
        )
        messages.success(request, 'Resource added successfully!')
        return redirect('admin_resources')
    
    context = {
        'resources': resources,
        'categories': Resource.CATEGORY_CHOICES,
        'resource_types': Resource.RESOURCE_TYPES,
    }
    return render(request, 'chatbot/admin_resources.html', context)

@staff_member_required
def admin_delete_resource(request, resource_id):
    """Delete a resource."""
    resource = get_object_or_404(Resource, id=resource_id)
    resource.delete()
    messages.success(request, 'Resource deleted successfully!')
    return redirect('admin_resources')

@staff_member_required
def admin_quizzes(request):
    """Manage quizzes."""
    quizzes = Quiz.objects.all().order_by('-created_at')
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        category = request.POST.get('category')
        difficulty = request.POST.get('difficulty')
        passing_score = request.POST.get('passing_score', 70)
        
        Quiz.objects.create(
            title=title,
            description=description,
            category=category,
            difficulty=difficulty,
            passing_score=passing_score,
            is_published=True
        )
        messages.success(request, 'Quiz added successfully!')
        return redirect('admin_quizzes')
    
    context = {
        'quizzes': quizzes,
        'categories': Quiz.CATEGORY_CHOICES,
        'difficulties': Quiz._meta.get_field('difficulty').choices,
    }
    return render(request, 'chatbot/admin_quizzes.html', context)

@staff_member_required
def admin_delete_quiz(request, quiz_id):
    """Delete a quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz.delete()
    messages.success(request, 'Quiz deleted successfully!')
    return redirect('admin_quizzes')

@staff_member_required
def admin_faqs(request):
    """Manage FAQs."""
    faqs = FAQ.objects.all().order_by('-created_at')
    if request.method == 'POST':
        question = request.POST.get('question')
        answer = request.POST.get('answer')
        category = request.POST.get('category')
        
        FAQ.objects.create(
            question=question,
            answer=answer,
            category=category
        )
        messages.success(request, 'FAQ added successfully!')
        return redirect('admin_faqs')
    
    context = {
        'faqs': faqs,
        'categories': FAQ.CATEGORY_CHOICES,
    }
    return render(request, 'chatbot/admin_faqs.html', context)

@staff_member_required
def admin_delete_faq(request, faq_id):
    """Delete an FAQ."""
    faq = get_object_or_404(FAQ, id=faq_id)
    faq.delete()
    messages.success(request, 'FAQ deleted successfully!')
    return redirect('admin_faqs')

    # ---------- ADMIN QUIZ QUESTIONS ----------

@staff_member_required
def admin_quiz_detail(request, quiz_id):
    """View quiz details and manage its questions."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = QuizQuestion.objects.filter(quiz=quiz).order_by('order')
    
    if request.method == 'POST':
        # Add new question
        question_text = request.POST.get('question_text')
        option_a = request.POST.get('option_a')
        option_b = request.POST.get('option_b')
        option_c = request.POST.get('option_c')
        option_d = request.POST.get('option_d')
        correct_answer = request.POST.get('correct_answer')
        order = request.POST.get('order', 0)
        
        if question_text and option_a and option_b and option_c and option_d:
            QuizQuestion.objects.create(
                quiz=quiz,
                question_text=question_text,
                option_a=option_a,
                option_b=option_b,
                option_c=option_c,
                option_d=option_d,
                correct_answer=correct_answer,
                order=questions.count()
            )
            messages.success(request, 'Question added successfully!')
            return redirect('admin_quiz_detail', quiz_id=quiz.id)
        else:
            messages.error(request, 'Please fill in all fields.')
    
    context = {
        'quiz': quiz,
        'questions': questions,
        'question_count': questions.count(),
    }
    return render(request, 'chatbot/admin_quiz_detail.html', context)

@staff_member_required
def admin_delete_question(request, question_id):
    """Delete a question from a quiz."""
    question = get_object_or_404(QuizQuestion, id=question_id)
    quiz_id = question.quiz.id
    question.delete()
    messages.success(request, 'Question deleted successfully!')
    return redirect('admin_quiz_detail', quiz_id=quiz_id)

@login_required
def edit_profile(request):
    """Edit user profile (avatar, bio, location)."""
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update bio and location
        bio = request.POST.get('bio', '')
        location = request.POST.get('location', '')
        profile.bio = bio
        profile.location = location
        
        # Update avatar if uploaded
        if 'avatar' in request.FILES:
            # Delete old avatar if it exists and is not default
            if profile.avatar and profile.avatar.name != 'avatars/default.png':
                try:
                    profile.avatar.delete(save=False)
                except:
                    pass
            profile.avatar = request.FILES['avatar']
        
        profile.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    context = {
        'profile': profile,
    }
    return render(request, 'chatbot/edit_profile.html', context)

@login_required
def delete_avatar(request):
    """Remove user avatar."""
    profile = request.user.profile
    if profile.avatar and profile.avatar.name != 'avatars/default.png':
        try:
            profile.avatar.delete(save=False)
        except:
            pass
        profile.avatar = None
        profile.save()
        messages.success(request, 'Avatar removed successfully!')
    return redirect('edit_profile')

# ---------- ADMIN USER MANAGEMENT ----------
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

@staff_member_required
def admin_users(request):
    """View all registered users with their activity."""
    users = User.objects.all().order_by('-date_joined')
    
    # Get user stats
    total_users = users.count()
    active_users = users.filter(last_login__gte=timezone.now() - timedelta(days=30)).count()
    new_users_this_week = users.filter(date_joined__gte=timezone.now() - timedelta(days=7)).count()
    
    context = {
        'users': users,
        'total_users': total_users,
        'active_users': active_users,
        'new_users_this_week': new_users_this_week,
    }
    return render(request, 'chatbot/admin_users.html', context)

@staff_member_required
def admin_toggle_user_status(request, user_id):
    """Toggle user active status (activate/deactivate)."""
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f'User {user.username} has been {status}.')
    return redirect('admin_users')

@staff_member_required
def admin_delete_user(request, user_id):
    """Delete a user account."""
    user = get_object_or_404(User, id=user_id)
    username = user.username
    user.delete()
    messages.success(request, f'User {username} has been deleted.')
    return redirect('admin_users')