from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login
from django.contrib import messages

# Create your views here.
User = get_user_model()

def welcome(request):
    return render(request,'welcome.html')

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        User.objects.create (
            username = username,
            email = email,
            password = password
        )
        return redirect('login')
    
    return render(request, 'register.html')

def login(request):
    if request.user.is_authenticated:
        return redirect('welcome')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        try:
            user_obj = User.objects.get(username=username)
            username = user_obj.username
        except User.DoesNotExist:
            username = None

        user = authenticate(request, username=username, password=password)

        if user is not None:
            #login(request, user)
            return redirect('welcome')
        else:
            messages.error(request, 'Invalid email or password. Please try again.')
    
    return render(request, 'login.html')