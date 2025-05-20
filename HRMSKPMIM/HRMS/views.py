from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from .models import (
    STAFF, EDUCATION, EXPERIENCE, ADDRESS, PAYROLL, 
    FEEDBACK, LEAVE_BALANCE, TIMEOFF, MANAGER, 
    RECRUITMENT, TEAM, TEAM_MEMBERSHIP, HR, POLICIES, ADMIN
)
import logging
import secrets
import hashlib
from django.http import HttpResponse, Http404
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
from datetime import datetime

# Create your views here.

# home
def index(request):
    context = {
        'page': 'index'  # Add context to help with template debugging
    }
    return render(request, 'index.html', context)

def login(request):
    return render(request, 'login.html')

def logout(request):
    request.session.flush()
    messages.info(request, "You have been logged out.")
    return redirect('login')

def login_process(request):
    if request.method == 'POST':
        id = request.POST.get('id') 
        password = request.POST.get('password')

        staff = search(STAFF, id)
        admin = search(ADMIN, id)
        manager = search(MANAGER, id)
        hr = search(HR, id)

        if staff:
            if check_password(password, staff.password):
                request.session['user_type'] = 'staff'
                request.session['user_id'] = staff.id
                return redirect('staffmenu')
            else:
                messages.error(request, "ID or password is incorrect")
        elif admin:
            if check_password(password, admin.password):
                request.session['user_type'] = 'admin'
                request.session['user_id'] = admin.id
                return redirect('adminmenu')
            else:
                messages.error(request, "ID or password is incorrect")
        elif manager:
            if check_password(password, manager.password):
                request.session['user_type'] = 'manager'
                request.session['user_id'] = manager.id
                return redirect('managermenu')
            else:
                messages.error(request, "ID or password is incorrect")
        elif hr:
            if check_password(password, hr.password):
                request.session['user_type'] = 'hr'
                request.session['user_id'] = hr.id
                return redirect('hrmenu')
            else:
                messages.error(request, "ID or password is incorrect")
        else:
            messages.error(request, "ID or password is incorrect")

    return render(request, 'login.html')

def search(model, user_id):
    try:
        return model.objects.get(id=user_id)
    except model.DoesNotExist:
        return None

# Create a logger
logger = logging.getLogger(__name__)

# Dictionary to store reset tokens: {token: {'id': user_id, 'type': user_type, 'expiry': datetime}}
password_reset_tokens = {}

def forgot_password(request):
    """
    View for handling forgot password requests.
    GET: Display the forgot password form
    POST: Process the forgot password request and redirect to reset page
    """
    # Check if there is already a popup animation request in the session
    show_popup = request.session.pop('show_popup', True)
    
    if request.method == 'POST':
        user_id = request.POST.get('id')
        email = request.POST.get('email')
        
        # Try to find the user in any of the user models
        user = None
        user_type = None
        
        # Check staff
        try:
            user = STAFF.objects.get(id=user_id, email=email)
            user_type = 'staff'
        except STAFF.DoesNotExist:
            pass
        
        # Check HR (assuming HR might not have email field)
        if not user:
            try:
                hr = HR.objects.get(id=user_id)
                # Since HR model might not have email, we'd need to validate another way
                # For now, we'll just accept the HR user without email validation
                user = hr
                user_type = 'hr'
            except HR.DoesNotExist:
                pass
        
        # Check Manager (assuming Manager might not have email field)
        if not user:
            try:
                manager = MANAGER.objects.get(id=user_id)
                # Since Manager model might not have email, we'd need to validate another way
                # For now, we'll just accept the Manager user without email validation
                user = manager
                user_type = 'manager'
            except MANAGER.DoesNotExist:
                pass
        
        # Check Admin (assuming Admin might not have email field)
        if not user:
            try:
                admin = ADMIN.objects.get(id=user_id)
                # Since Admin model might not have email, we'd need to validate another way
                # For now, we'll just accept the Admin user without email validation
                user = admin
                user_type = 'admin'
            except ADMIN.DoesNotExist:
                pass
        
        if not user:
            messages.error(request, 'No account found with that ID.')
            return render(request, 'forgot_password.html')
        
        # Generate a secure token
        token = secrets.token_urlsafe(16)  # Shorter token for easier copying
        
        # Store token with user info and expiry time (24 hours from now)
        password_reset_tokens[token] = {
            'id': user_id,
            'type': user_type,
            'expiry': timezone.now() + timedelta(minutes=2)
        }
        
        # Add a success message for the next page
        messages.success(request, 'Your identity has been verified. Please create a new password.')
        
        # Redirect directly to the reset page
        return redirect('reset_password', token=token)
    
    # GET request - just show the form with animation if needed
    return render(request, 'forgot_password.html', {'show_popup': show_popup})

def reset_password(request, token):
    """
    View for handling password reset with a token.
    GET: Display the password reset form
    POST: Process the password reset
    """
    # Check if token exists and is valid
    if token not in password_reset_tokens:
        messages.error(request, "Invalid or expired password reset link.")
        return redirect('forgot_password')
    
    token_data = password_reset_tokens[token]
    
    # Check if token has expired
    if token_data['expiry'] < timezone.now():
        # Remove expired token
        del password_reset_tokens[token]
        messages.error(request, "Password reset link has expired. Please try again.")
        return redirect('forgot_password')
    
    # Check if there is already a popup animation request in the session
    show_popup = request.session.pop('show_popup', True)
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validate passwords
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'reset_password.html', {
                'token': token,
                'show_popup': show_popup
            })
        
        # Basic password strength validation
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'reset_password.html', {
                'token': token,
                'show_popup': show_popup
            })
        
        # Hash the new password - in a real app, use Django's built-in password hashing
        hashed_password = make_password(new_password)
        
        user_id = token_data['id']
        user_type = token_data['type']
        
        # Update the user's password based on user type
        try:
            if user_type == 'staff':
                user = STAFF.objects.get(id=user_id)
                user.password = hashed_password
                user.save()
            elif user_type == 'hr':
                user = HR.objects.get(id=user_id)
                user.password = hashed_password
                user.save()
            elif user_type == 'manager':
                user = MANAGER.objects.get(id=user_id)
                user.password = hashed_password
                user.save()
            elif user_type == 'admin':
                user = ADMIN.objects.get(id=user_id)
                user.password = hashed_password
                user.save()
            else:
                messages.error(request, 'Invalid user type.')
                return render(request, 'reset_password.html', {
                    'token': token,
                    'show_popup': show_popup
                })
                
            # Remove the used token
            del password_reset_tokens[token]
            
            # Show success message and redirect to login page
            messages.success(request, 'Your password has been successfully reset. You can now log in with your new password.')
            return redirect('login')  
            
        except (STAFF.DoesNotExist, HR.DoesNotExist, MANAGER.DoesNotExist, ADMIN.DoesNotExist):
            messages.error(request, 'User not found.')
            return render(request, 'reset_password.html', {
                'token': token,
                'show_popup': show_popup
            })
    
    # GET request - just show the form
    return render(request, 'reset_password.html', {'token': token, 'show_popup': show_popup})

# admin

def adminmenu(request):
    user_id = request.session.get('user_id')
    
    if not request.session.get('user_type') == 'admin':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get the admin information from the database
        admin = ADMIN.objects.get(id=user_id)
        
        # Create context for the template
        context = {
            'admin': admin,
        }
        
        # Render the admin menu page with the context
        return render(request, 'admin/adminmenu.html', context)
    
    except ADMIN.DoesNotExist:
        # If admin record doesn't exist, log out and redirect
        request.session.flush()
        messages.error(request, "Admin account not found. Please login again.")
        return redirect('login')
    except Exception as e:
        # Handle any other exceptions
        request.session.flush()
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('login')

def admin_profile(request):
    user_id = request.session.get('user_id')
    
    if not request.session.get('user_type') == 'admin':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    admin = ADMIN.objects.get(id=user_id)
    # Handle form submission
    if request.method == 'POST':
        name = request.POST.get('name')
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        

        # Update name
        if name and name != admin.name:
            admin.name = name
            admin.save()
            messages.success(request, 'Name updated successfully!')
        
        # Update password if provided
        if current_password and new_password and confirm_password:
            if check_password(current_password, admin.password):
                if new_password == confirm_password:
                    admin.password = make_password(new_password)
                    admin.save()
                    messages.success(request, 'Password updated successfully!')
                else:
                    messages.error(request, 'New password and confirm password do not match!')
            else:
                messages.error(request, 'Current password is incorrect!')
                
    context = {
        'admin': admin
    }
    return render(request, 'admin/profile.html', context)

# Add these functions to your admin/views.py file

def user_management(request):
    """View for the user management page"""
    admin_id = request.session.get('user_id')
    
    if not request.session.get('user_type') == 'admin':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
   
    admin = ADMIN.objects.get(id=admin_id)

    staffs = STAFF.objects.all()
    managers = MANAGER.objects.all()
    hrs = HR.objects.all()    
    
    context = {
        'admin': admin,
        'staffs': staffs,
        'managers': managers,
        'hrs': hrs,
    }
    return render(request, 'admin/user_management.html', context)

def add_user(request):
    """
    Handles the addition of new users (staff, managers, HR).
    Validates form data and creates new user records.
    """
    if not request.session.get('user_type') == 'admin':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    if request.method == 'POST':
        user_type = request.POST.get('user_type')
        user_id = request.POST.get('id')
        name = request.POST.get('name')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # Basic validation
        if not user_id or not name or not password:
            messages.error(request, 'All fields are required')
            return redirect('user_management')
        
        # Check if passwords match
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return redirect('user_management')
        
        # Validate password strength
        if not validate_password_strength(password):
            messages.error(request, 'Password must be at least 8 characters with a capital letter, number, and symbol')
            return redirect('user_management')
        
        # Check if ID already exists in any of the user tables
        # This ensures IDs are unique across all user types
        if STAFF.objects.filter(id=user_id).exists() or MANAGER.objects.filter(id=user_id).exists() or HR.objects.filter(id=user_id).exists() or ADMIN.objects.filter(id=user_id).exists():
            messages.error(request, f'ID {user_id} is already taken. Please choose a different ID.')
            return redirect('user_management')
        
        # Hash the password for security
        hashed_password = make_password(password)
        
        # Process based on user type
        if user_type == 'staff':
            # Get date of birth for staff
            date_of_birth = request.POST.get('date_of_birth')
            
            # Validate date format
            try:
                if date_of_birth:
                    dob_date = parse_date(date_of_birth)
                else:
                    messages.error(request, 'Date of birth is required for staff')
                    return redirect('user_management')
            except:
                messages.error(request, 'Invalid date format')
                return redirect('user_management')
            
            # Create new staff
            try:
                staff = STAFF(
                    id=user_id,
                    name=name,
                    password=hashed_password,
                    date_of_birth=dob_date,
                    # Set default values for other required fields
                    phone='',
                    email='',
                    status='',
                    gender='',
                    bank_number='',
                    emergency_contact=''
                )
                staff.save()
                messages.success(request, f'Staff {name} added successfully')
            except Exception as e:
                messages.error(request, f'Error adding staff: {str(e)}')
            
        elif user_type == 'manager':
            staff_id = request.POST.get('staff_id')
            
            # Check if staff exists
            try:
                staff = STAFF.objects.get(id=staff_id)
            except STAFF.DoesNotExist:
                messages.error(request, f'Staff ID {staff_id} does not exist')
                return redirect('user_management')
            
            # Create new manager
            try:
                manager = MANAGER(
                    id=user_id,
                    name=name,
                    password=hashed_password,
                    staffid=staff
                )
                manager.save()
                messages.success(request, f'Manager {name} added successfully')
                managers = MANAGER.objects.get(id=user_id)
                team = TEAM(
                    managerid = managers,
                )
                team.save()
            except Exception as e:
                messages.error(request, f'Error adding manager: {str(e)}')
            
        elif user_type == 'hr':
            staff_id = request.POST.get('staff_id')
            
            # Check if staff exists
            try:
                staff = STAFF.objects.get(id=staff_id)
            except STAFF.DoesNotExist:
                messages.error(request, f'Staff ID {staff_id} does not exist')
                return redirect('user_management')
            
            # Create new HR
            try:
                hr = HR(
                    id=user_id,
                    name=name,
                    password=hashed_password,
                    staffid=staff
                )
                hr.save()
                messages.success(request, f'HR {name} added successfully')
            except Exception as e:
                messages.error(request, f'Error adding HR: {str(e)}')
        
        return redirect('user_management')
    
    # If not POST, redirect back to user management page
    return redirect('user_management')

def delete_user(request):
    """Handle deleting a user"""
    user_type = request.GET.get('type')
    user_id = request.GET.get('id')
    
    if not user_type or not user_id:
        messages.error(request, 'Invalid request!')
        return redirect('user_management')
    
    try:
        if user_type == 'staff':
            staff = STAFF.objects.get(id=user_id)
            staff.delete()
            messages.success(request, f'Staff user {user_id} deleted successfully!')
        
        elif user_type == 'manager':
            manager = MANAGER.objects.get(id=user_id)
            manager.delete()
            messages.success(request, f'Manager user {user_id} deleted successfully!')
        
        elif user_type == 'hr':
            hr = HR.objects.get(id=user_id)
            hr.delete()
            messages.success(request, f'HR user {user_id} deleted successfully!')
        
        else:
            messages.error(request, 'Invalid user type!')
    
    except (STAFF.DoesNotExist, MANAGER.DoesNotExist, HR.DoesNotExist):
        messages.error(request, f'User {user_id} not found!')
    
    return redirect('user_management')

def validate_password_strength(password):
    """
    Validates that the password meets the required strength criteria:
    - At least 8 characters
    - Contains at least one uppercase letter
    - Contains at least one number
    - Contains at least one special character
    """
    if len(password) < 8:
        return False
    
    # Check for uppercase letter
    if not any(char.isupper() for char in password):
        return False
    
    # Check for digit
    if not any(char.isdigit() for char in password):
        return False
    
    # Check for special character
    if not any(not char.isalnum() for char in password):
        return False
    
    return True


# hr
def hrmenu(request):
    # Check if user is authorized as HR
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    # Get HR information to display in header
    hr_id = request.session.get('user_id')
    try:
        hr = HR.objects.get(id=hr_id)
    except HR.DoesNotExist:
        hr = None
    
    # If user is authorized, render the HR menu page
    return render(request, 'hr/hrmenu.html', {'hr': hr})

def employee_management(request):
    """View for the user management page"""
    hr_id = request.session.get('user_id')
    
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
   
    hr = HR.objects.get(id=hr_id)

    staffs = STAFF.objects.all()
    managers = MANAGER.objects.all()
    hrs = HR.objects.all()    
    
    context = {
        'hr': hr,
        'staffs': staffs,
        'managers': managers,
        'hrs': hrs,
    }
    return render(request, 'hr/employee_management.html', context)

def add_employee(request):
    """
    Handles the addition of new users (staff, managers, HR).
    Validates form data and creates new user records.
    """
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    if request.method == 'POST':
        user_type = request.POST.get('user_type')
        user_id = request.POST.get('id')
        name = request.POST.get('name')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # Basic validation
        if not user_id or not name or not password:
            messages.error(request, 'All fields are required')
            return redirect('employee_management')
        
        # Check if passwords match
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return redirect('employee_management')
        
        # Validate password strength
        if not validate_password_strength(password):
            messages.error(request, 'Password must be at least 8 characters with a capital letter, number, and symbol')
            return redirect('employee_management')
        
        # Check if ID already exists in any of the user tables
        # This ensures IDs are unique across all user types
        if STAFF.objects.filter(id=user_id).exists() or MANAGER.objects.filter(id=user_id).exists() or HR.objects.filter(id=user_id).exists() or ADMIN.objects.filter(id=user_id).exists():
            messages.error(request, f'ID {user_id} is already taken. Please choose a different ID.')
            return redirect('employee_management')
        
        # Hash the password for security
        hashed_password = make_password(password)
        
        # Process based on user type
        if user_type == 'staff':
            # Get date of birth for staff
            date_of_birth = request.POST.get('date_of_birth')
            
            # Validate date format
            try:
                if date_of_birth:
                    dob_date = parse_date(date_of_birth)
                else:
                    messages.error(request, 'Date of birth is required for staff')
                    return redirect('employee_management')
            except:
                messages.error(request, 'Invalid date format')
                return redirect('employee_management')
            
            # Create new staff
            try:
                staff = STAFF(
                    id=user_id,
                    name=name,
                    password=hashed_password,
                    date_of_birth=dob_date,
                    # Set default values for other required fields
                    phone='',
                    email='',
                    status='',
                    gender='',
                    bank_number='',
                    emergency_contact=''
                )
                staff.save()
                messages.success(request, f'Staff {name} added successfully')
            except Exception as e:
                messages.error(request, f'Error adding staff: {str(e)}')
            
        elif user_type == 'manager':
            staff_id = request.POST.get('staff_id')
            
            # Check if staff exists
            try:
                staff = STAFF.objects.get(id=staff_id)
            except STAFF.DoesNotExist:
                messages.error(request, f'Staff ID {staff_id} does not exist')
                return redirect('employee_management')
            
            # Create new manager
            try:
                manager = MANAGER(
                    id=user_id,
                    name=name,
                    password=hashed_password,
                    staffid=staff
                )
                manager.save()
                messages.success(request, f'Manager {name} added successfully')
                managers = MANAGER.objects.get(id=user_id)
                team = TEAM(
                    managerid = managers,
                )
                team.save()
            except Exception as e:
                messages.error(request, f'Error adding manager: {str(e)}')
            
        elif user_type == 'hr':
            staff_id = request.POST.get('staff_id')
            
            # Check if staff exists
            try:
                staff = STAFF.objects.get(id=staff_id)
            except STAFF.DoesNotExist:
                messages.error(request, f'Staff ID {staff_id} does not exist')
                return redirect('employee_management')
            
            # Create new HR
            try:
                hr = HR(
                    id=user_id,
                    name=name,
                    password=hashed_password,
                    staffid=staff
                )
                hr.save()
                messages.success(request, f'HR {name} added successfully')
            except Exception as e:
                messages.error(request, f'Error adding HR: {str(e)}')
        
        return redirect('employee_management')
    
    # If not POST, redirect back to user management page
    return redirect('employee_management')

def delete_employee(request):
    """Handle deleting a user"""
    user_type = request.GET.get('type')
    user_id = request.GET.get('id')
    
    if not user_type or not user_id:
        messages.error(request, 'Invalid request!')
        return redirect('employee_management')
    
    try:
        if user_type == 'staff':
            staff = STAFF.objects.get(id=user_id)
            staff.delete()
            messages.success(request, f'Staff user {user_id} deleted successfully!')
        
        elif user_type == 'manager':
            manager = MANAGER.objects.get(id=user_id)
            manager.delete()
            messages.success(request, f'Manager user {user_id} deleted successfully!')
        
        elif user_type == 'hr':
            hr = HR.objects.get(id=user_id)
            hr.delete()
            messages.success(request, f'HR user {user_id} deleted successfully!')
        
        else:
            messages.error(request, 'Invalid user type!')
    
    except (STAFF.DoesNotExist, MANAGER.DoesNotExist, HR.DoesNotExist):
        messages.error(request, f'User {user_id} not found!')
    
    return redirect('employee_management')

def hr_profile(request):
    user_id = request.session.get('user_id')
    
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    hr = HR.objects.get(id=user_id)
    # Handle form submission
    if request.method == 'POST':
        name = request.POST.get('name')
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        

        # Update name
        if name and name != hr.name:
            hr.name = name
            hr.save()
            messages.success(request, 'Name updated successfully!')
        
        # Update password if provided
        if current_password and new_password and confirm_password:
            if check_password(current_password, hr.password):
                if new_password == confirm_password:
                    hr.password = make_password(new_password)
                    hr.save()
                    messages.success(request, 'Password updated successfully!')
                else:
                    messages.error(request, 'New password and confirm password do not match!')
            else:
                messages.error(request, 'Current password is incorrect!')
                
    context = {
        'hr': hr
    }
    return render(request, 'hr/profile.html', context)