from django.contrib.auth import login, authenticate, logout
from django.contrib.messages import get_messages  # <-- Add this
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
from google import genai

from .models import FAQ, ChatSession, ChatMessage, Resource, Quiz, QuizQuestion, QuizAttempt, QuizResponse

# --- Configure Gemini ---
client = genai.Client(api_key=settings.GEMINI_API_KEY)
MODEL_NAME = 'gemini-2.5-flash'

# --- Memory Limit ---
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
    for msg in reversed(messages):  # oldest to newest
        role = 'user' if not msg.is_bot else 'assistant'
        history.append({'role': role, 'content': msg.message})
    return history

def get_faq_fallback(user_message):
    """Check FAQ database for matches."""
    clean_msg = re.sub(r'[^\w\s]', '', user_message.lower())
    user_words = set(clean_msg.split())
    
    all_faqs = FAQ.objects.all()
    best_match = None
    best_score = 0
    
    for faq in all_faqs:
        faq_words = set(faq.question.lower().split())
        matches = len(user_words.intersection(faq_words))
        
        # Bonus for exact phrase match
        if user_message.lower() in faq.question.lower():
            matches += 10
        
        if matches > best_score:
            best_score = matches
            best_match = faq
    
    # Require at least 3 matching words to consider it a good match
    if best_match and best_score >= 3:
        return best_match.answer
    
    # Return None to indicate no good FAQ match
    return None
    """Fallback FAQ matching."""
    print(f"🟡 Using FAQ fallback for: {user_message}")
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
    """Smart hybrid: FAQ first, Gemini fallback."""
    
    # --- STEP 1: CHECK FAQ DATABASE FIRST ---
    faq_answer = get_faq_fallback(user_message)
    
    # If FAQ has a good match (not the generic fallback message), use it
    if faq_answer and "I don't have a specific answer" not in faq_answer:
        print(f"✅ Using FAQ answer for: {user_message}")
        return faq_answer
    
    # --- STEP 2: NO FAQ MATCH - TRY GEMINI ---
    print(f"🔵 No FAQ match. Trying Gemini for: {user_message}")
    
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
    
    # --- STEP 3: RETRY LOGIC FOR GEMINI ---
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            
            raw_response = response.text
            formatted_response = raw_response.replace('\n\n', '<br><br>').replace('\n', '<br>')
            
            print(f"🟢 Gemini response received!")
            return formatted_response
            
        except Exception as e:
            error_msg = str(e)
            print(f"🔴 Attempt {attempt + 1} failed: {error_msg[:80]}...")
            
            if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 10  # 10s, 20s
                    print(f"⏳ Rate limited. Waiting {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                else:
                    return ("I'm currently handling a high volume of requests. "
                            "Please wait a moment and try again. "
                            "In the meantime, check out our Learning Hub for resources on "
                            "digital rights, AI policy, and cybersecurity in Uganda!")
            else:
                return ("I couldn't find an answer to that question. "
                        "Please check our Learning Hub for more information, "
                        "or try rephrasing your question.")
    
    return ("I'm having trouble answering right now. "
            "Please explore our Learning Hub or try again in a moment.")
    """Generate response with conversation memory and automatic retry."""
    
    # --- Build the prompt (your existing code) ---
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
    
    # --- RETRY LOOP ---
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"🔵 Attempt {attempt + 1}: Sending to Gemini...")
            
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            
            raw_response = response.text
            
            # Format for readability
            formatted_response = raw_response.replace('\n\n', '<br><br>').replace('\n', '<br>')
            
            print(f"🟢 Gemini response received!")
            return formatted_response
            
        except Exception as e:
            error_msg = str(e)
            print(f"🔴 Attempt {attempt + 1} failed: {error_msg[:100]}...")
            
            # Check if it's a rate limit error (429)
            if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                if attempt < max_attempts - 1:
                    # Wait before retrying (increases with each attempt)
                    wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                    print(f"⏳ Rate limited. Waiting {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                else:
                    # Last attempt failed - show friendly message
                    return ("I'm currently handling a high volume of requests. "
                            "Please wait a moment and try again. "
                            "In the meantime, check out our Learning Hub for resources on "
                            "digital rights, AI policy, and cybersecurity in Uganda!")
            else:
                # Other error - use FAQ fallback
                return get_faq_fallback(user_message)
    
    # If all retries fail, fallback to FAQ
    return get_faq_fallback(user_message)
    """Generate response with conversation memory."""
    try:
        # Build prompt with history
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
        
        print(f"🔵 Sending to Gemini: {user_message}")
        
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        
        raw_response = response.text
        
        # --- FORMAT FOR READABILITY ---
        # Convert newlines to HTML line breaks
        formatted_response = raw_response.replace('\n\n', '<br><br>').replace('\n', '<br>')
        
        print(f"🟢 Gemini response received and formatted")
        return formatted_response
        
    except Exception as e:
        print(f"🔴 Gemini error: {e}")
        import traceback
        traceback.print_exc()
        return get_faq_fallback(user_message)
    """Generate response with conversation memory."""
    try:
        # --- Build a simple prompt with history ---
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

IMPORTANT RULES:
- ONLY answer questions about digital rights, internet governance, AI policy, data privacy, and cybersecurity in Uganda.
- For questions about politics, sports, entertainment, or general knowledge, politely say: "I'm sorry, I'm only trained to answer questions about digital rights, internet governance, AI policy, data privacy, and cybersecurity in Uganda. Please ask me about those topics!"
- Always mention Ugandan context (laws, institutions like NITA-U, UCC, CERT-UG, etc.).

Conversation history:
{history_text}

User: {user_message}

Assistant:"""
        
        print(f"🔵 Sending to Gemini: {user_message}")
        
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        
        print(f"🟢 Gemini response received: {response.text[:50]}...")
        return response.text
        
    except Exception as e:
        print(f"🔴 Gemini error: {e}")
        import traceback
        traceback.print_exc()
        return get_faq_fallback(user_message)

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
            # If everything fails, send a graceful error
            return JsonResponse({
                'error': 'I\'m having trouble connecting. Please try again in a moment.'
            }, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            session_id = data.get('session_id')
            if not user_message:
                return JsonResponse({'error': 'Empty message'}, status=400)

            # Get or create session
            if session_id:
                session, created = ChatSession.objects.get_or_create(session_id=session_id)
            else:
                session = ChatSession.objects.create(session_id=str(uuid.uuid4()))

            # Save user message
            ChatMessage.objects.create(session=session, message=user_message, is_bot=False)

            # Get history
            history = get_conversation_history(session)

            # Get bot response with memory
            bot_response = get_gemini_response_with_memory(user_message, history)

            # Save bot response
            ChatMessage.objects.create(session=session, message=bot_response, is_bot=True)

            return JsonResponse({
                'response': bot_response,
                'session_id': session.session_id
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

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
    """User logout view - clears old messages and shows logout confirmation."""
    
    # --- Clear all existing messages first ---
    storage = get_messages(request)
    for _ in storage:
        pass  # This clears all messages
    
    # --- Log the user out ---
    logout(request)
    
    # --- Add fresh logout message ---
    messages.success(request, 'You have been logged out successfully.')
    
    # --- Redirect to home ---
    return redirect('chat_home')
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
    """User logout view."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('chat_home')  # This goes to index.html
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')

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