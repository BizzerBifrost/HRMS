from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages

# Create your views here.

def index(request):
    context = {
        'page': 'index'  # Add context to help with template debugging
    }
    return render(request, 'index.html', context)

def login(request):
    return render(request, 'login.html')

def login_process(request):
    # if request.method == 'POST':
    #     id = request.POST.get('id') #ni ambik dari yang input name contoh:<input type='text' name='EMAIL'> jangan ikut bold just nak tunjuk je
    #     password = request.POST.get('password')

    #     user = search(User, email)
    #     staff = search(Staff, email)
    #     admin = search(Admin, email)

    #     if user:
    #         if user.password == password:
    #             request.session['user_type'] = 'user' # ni declare user type je tukar ikut user type website 
    #             request.session['user_id'] = user.userID  
    #             return redirect('usermenu')
    #         else:
    #             messages.error(request, "ID or password is incorrect")
    #     elif staff:
    #         if staff.password == password:
    #             request.session['user_type'] = 'staff'
    #             request.session['user_id'] = staff.staffID
    #             return redirect('staffmenu')
    #         else:
    #             messages.error(request, "ID or password is incorrect")
    #     elif admin:
    #         if admin.password == password:
    #             request.session['user_type'] = 'admin'
    #             request.session['user_id'] = admin.adminID
    #             return redirect('adminmenu')
    #         else:
    #             messages.error(request, "ID or password is incorrect")
    #     else:
    #         messages.error(request, "ID or password is incorrect")
    return render(request, 'login.html')

def search(model, id):
    try:
        return model.objects.get(id=id)
    except model.DoesNotExist:
        return None

def forgot_password(request):
    return render(request, 'forgot_password.html')