from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError

# Create your views here.
User = get_user_model()

def welcome(request):
    return render(request,'welcome.html')

def register_user(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username','').strip()
        email = request.POST.get('email','').strip()
        password = request.POST.get('password','')

        if not username or not password or not email:
            messages.error(request, 'Please enter all details.')
            return render(request, 'register.html')

        try:
            #create_user() automatically hashes password unlike create()
            User.objects.create_user(
                username = username,
                email = email,
                password = password
            )
            messages.success(request, 'Registration successful. Please log in.')
            return redirect('login')
        except IntegrityError:
            messages.error(request, 'A user with that username or email already exists.')
    
    return render(request, 'register.html')

def login_user(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)  # 2 weeks in seconds
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid email or password. Please try again.')
    
    return render(request, 'login.html')

def logout_user(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')

@login_required
def dashboard(request):
    return render(request, 'dashboard.html')
