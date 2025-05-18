from django.shortcuts import render

# Create your views here.

def index(request):
    context = {
        'page': 'index'  # Add context to help with template debugging
    }
    return render(request, 'index.html', context)

def login(request):
    return render(request, 'login.html')