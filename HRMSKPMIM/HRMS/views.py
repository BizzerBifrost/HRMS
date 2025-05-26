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
from decimal import Decimal
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
import json


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
        position = request.POST.get('position')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        

        
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
                    position = position,
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
                    password=hashed_password,
                    staffid=staff
                )
                manager.save()
                user = MANAGER.objects.get(id=user_id)
                messages.success(request, f'Manager {user.staffid.name} added successfully')
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
                    password=hashed_password,
                    staffid=staff
                )
                hr.save()
                user = HR.objects.get(id=user_id)
                messages.success(request, f'HR {user.staffid.name} added successfully')
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
        position = request.POST.get('position')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        
        
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
                    position = position,
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
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
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

def update_staff(request, staff_id):
    """View for updating staff information"""
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        staff = STAFF.objects.get(id=staff_id)
    except STAFF.DoesNotExist:
        messages.error(request, 'Staff not found.')
        return redirect('employee_management')
    
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name', '').strip()
        position = request.POST.get('position', '').strip()
        gender = request.POST.get('gender', '')
        
        # Password handling
        new_password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        
        try:
            # Update staff information
            staff.name = name
            staff.position = position
            staff.gender = gender
            
            
            staff.save()
            
            messages.success(request, f'Staff {staff.name} has been updated successfully.')
            return redirect('employee_management')
            
        except Exception as e:
            messages.error(request, f'Error updating staff: {str(e)}')
            hr_id = request.session.get('user_id')
            hr = HR.objects.get(id=hr_id)
            return render(request, 'hr/update_staff.html', {'staff': staff, 'hr': hr})
    
    # GET request - display the form
    hr_id = request.session.get('user_id')
    hr = HR.objects.get(id=hr_id)
    
    context = {
        'staff': staff,
        'hr': hr
    }
    return render(request, 'hr/update_staff.html', context)


def payroll(request):
    # Check if user is authorized (HR only)
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get HR information from session
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        
        # Get all staff members
        staff_list = STAFF.objects.all()
        
        # Handle search functionality
        search_id = request.GET.get('search_id', '').strip()
        search_name = request.GET.get('search_name', '').strip()
        search_position = request.GET.get('search_position', '').strip()
        
        # Apply filters if search parameters are provided
        if search_id:
            staff_list = staff_list.filter(id__icontains=search_id)
        
        if search_name:
            staff_list = staff_list.filter(name__icontains=search_name)
        
        if search_position:
            staff_list = staff_list.filter(position__icontains=search_position)
        
        # Order by staff ID for consistent display
        staff_list = staff_list.order_by('id')
        
        context = {
            'staff_list': staff_list,
            'hr': hr,
            'search_performed': bool(search_id or search_name or search_position),
        }
        
        return render(request, 'hr/payroll.html', context)
    
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hrmenu')
    
def set_payroll(request, staff_id):
    # Check if user is authorized (HR only)
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get HR information from session
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        
        # Get staff member
        staff = get_object_or_404(STAFF, id=staff_id)
        
        # Check if payroll already exists for this staff
        existing_payroll = PAYROLL.objects.filter(staffid=staff).first()
        if existing_payroll:
            messages.warning(request, f"Payroll already exists for {staff.name}. Please use edit function instead.")
            return redirect('payroll')
        
        if request.method == 'POST':
            try:
                # Get form data
                base = Decimal(request.POST.get('base', '0.00'))
                bonus = Decimal(request.POST.get('bonus', '0.00'))
                allowance = Decimal(request.POST.get('allowance', '0.00'))
                pcb = Decimal(request.POST.get('pcb', '0.00'))
                
                # Validate input values
                if base < 0 or bonus < 0 or allowance < 0 or pcb < 0:
                    messages.error(request, "All payroll amounts must be positive numbers.")
                    return render(request, 'hr/set_payroll.html', {
                        'staff': staff,
                        'hr': hr,
                    })
                
                if base == 0:
                    messages.error(request, "Base salary cannot be zero.")
                    return render(request, 'hr/set_payroll.html', {
                        'staff': staff,
                        'hr': hr,
                    })
                
                # Create new payroll record
                # Note: The PAYROLL model automatically calculates EPF and net salary in its save method
                payroll = PAYROLL.objects.create(
                    staffid=staff,
                    base=base,
                    bonus=bonus,
                    allowance=allowance,
                    pcb=pcb
                )
                
                messages.success(request, f"Payroll successfully set for {staff.name}. Net salary: RM{payroll.net_salary:.2f}")
                return redirect('payroll')
                
            except ValueError:
                messages.error(request, "Please enter valid numerical values for all payroll fields.")
                return render(request, 'hr/set_payroll.html', {
                    'staff': staff,
                    'hr': hr,
                })
            except Exception as e:
                messages.error(request, f"An error occurred while setting payroll: {str(e)}")
                return render(request, 'hr/set_payroll.html', {
                    'staff': staff,
                    'hr': hr,
                })
        
        # GET request - show the form
        context = {
            'staff': staff,
            'hr': hr,
        }
        
        return render(request, 'hr/set_payroll.html', context)
    
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('payroll')
    
def view_payroll(request, staff_id):
    # Check if user is authorized (HR only)
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get HR information from session
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        
        # Get staff member
        staff = get_object_or_404(STAFF, id=staff_id)
        
        # Get payroll information
        payroll = get_object_or_404(PAYROLL, staffid=staff)
        
        context = {
            'staff': staff,
            'hr': hr,
            'payroll': payroll,
        }
        
        return render(request, 'hr/view_payroll.html', context)
        
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('payroll')

def edit_payroll(request, staff_id):
    # Check if user is authorized (HR only)
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get HR information from session
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        
        # Get staff member
        staff = get_object_or_404(STAFF, id=staff_id)
        
        # Get payroll information
        payroll = get_object_or_404(PAYROLL, staffid=staff)
        
        if request.method == 'POST':
            try:
                # Store original values for comparison
                original_base = payroll.base
                original_bonus = payroll.bonus
                original_allowance = payroll.allowance
                original_pcb = payroll.pcb
                original_net_salary = payroll.net_salary
                
                # Get form data
                new_base = Decimal(request.POST.get('base', '0.00'))
                new_bonus = Decimal(request.POST.get('bonus', '0.00'))
                new_allowance = Decimal(request.POST.get('allowance', '0.00'))
                new_pcb = Decimal(request.POST.get('pcb', '0.00'))
                
                # Validate input values
                if new_base < 0 or new_bonus < 0 or new_allowance < 0 or new_pcb < 0:
                    messages.error(request, "All payroll amounts must be positive numbers.")
                    return render(request, 'hr/edit_payroll.html', {
                        'staff': staff,
                        'hr': hr,
                        'payroll': payroll,
                    })
                
                if new_base == 0:
                    messages.error(request, "Base salary cannot be zero.")
                    return render(request, 'hr/edit_payroll.html', {
                        'staff': staff,
                        'hr': hr,
                        'payroll': payroll,
                    })
                
                # Check if any values have actually changed
                changes_made = (
                    new_base != original_base or 
                    new_bonus != original_bonus or 
                    new_allowance != original_allowance or 
                    new_pcb != original_pcb
                )
                
                if not changes_made:
                    messages.info(request, "No changes were made to the payroll information.")
                    return redirect('view_payroll', staff_id=staff.id)
                
                # Update payroll record
                payroll.base = new_base
                payroll.bonus = new_bonus
                payroll.allowance = new_allowance
                payroll.pcb = new_pcb
                # The save method will automatically recalculate EPF and net salary
                payroll.save()
                
                # Create success message with details of changes
                change_details = []
                if new_base != original_base:
                    change_details.append(f"Base salary: RM{original_base} → RM{new_base}")
                if new_bonus != original_bonus:
                    change_details.append(f"Bonus: RM{original_bonus} → RM{new_bonus}")
                if new_allowance != original_allowance:
                    change_details.append(f"Allowance: RM{original_allowance} → RM{new_allowance}")
                if new_pcb != original_pcb:
                    change_details.append(f"PCB Tax: RM{original_pcb} → RM{new_pcb}")
                
                # Add net salary change
                net_salary_change = payroll.net_salary - original_net_salary
                if net_salary_change != 0:
                    sign = "+" if net_salary_change > 0 else ""
                    change_details.append(f"Net salary: RM{original_net_salary} → RM{payroll.net_salary} ({sign}RM{net_salary_change})")
                
                success_message = f"Payroll successfully updated for {staff.name}. Changes: {'; '.join(change_details)}"
                messages.success(request, success_message)
                
                return redirect('view_payroll', staff_id=staff.id)
                
            except ValueError:
                messages.error(request, "Please enter valid numerical values for all payroll fields.")
                return render(request, 'hr/edit_payroll.html', {
                    'staff': staff,
                    'hr': hr,
                    'payroll': payroll,
                })
            except Exception as e:
                messages.error(request, f"An error occurred while updating payroll: {str(e)}")
                return render(request, 'hr/edit_payroll.html', {
                    'staff': staff,
                    'hr': hr,
                    'payroll': payroll,
                })
        
        # GET request - show the form
        context = {
            'staff': staff,
            'hr': hr,
            'payroll': payroll,
        }
        
        return render(request, 'hr/edit_payroll.html', context)
        
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('payroll')
    
def hr_policies(request):
    # Check if user is authenticated and is HR
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    # Get HR user from session
    hr_id = request.session.get('user_id')
    if not hr_id:
        request.session.flush()
        messages.error(request, "Session expired. Please login again")
        return redirect('login')
    
    try:
        hr = HR.objects.get(id=hr_id)
    except HR.DoesNotExist:
        request.session.flush()
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    
    # Handle POST requests for CRUD operations
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_policy':
            # Add new policy
            policy_text = request.POST.get('policy_text', '').strip()
            
            if policy_text:
                try:
                    POLICIES.objects.create(
                        policies=policy_text
                    )
                    messages.success(request, 'Policy added successfully!')
                except Exception as e:
                    messages.error(request, f'Error adding policy: {str(e)}')
            else:
                messages.error(request, 'Policy content cannot be empty.')
        
        elif action == 'edit_policy':
            # Edit existing policy
            policy_id = request.POST.get('policy_id')
            policy_text = request.POST.get('policy_text', '').strip()
            
            if policy_id and policy_text:
                try:
                    policy = get_object_or_404(POLICIES, id=policy_id)
                    policy.policies = policy_text
                    policy.save()
                    messages.success(request, 'Policy updated successfully!')
                except Exception as e:
                    messages.error(request, f'Error updating policy: {str(e)}')
            else:
                messages.error(request, 'Invalid policy data provided.')
        
        elif action == 'delete_policy':
            # Delete policy
            policy_id = request.POST.get('policy_id')
            
            if policy_id:
                try:
                    policy = get_object_or_404(POLICIES, id=policy_id)
                    policy.delete()
                    messages.success(request, 'Policy deleted successfully!')
                except Exception as e:
                    messages.error(request, f'Error deleting policy: {str(e)}')
            else:
                messages.error(request, 'Invalid policy ID provided.')
        
        # Redirect to prevent form resubmission
        return redirect('hr_policies')
    
    # Get all policies ordered by most recent first
    policies = POLICIES.objects.all().order_by('-enacted')
    
    context = {
        'hr': hr,
        'policies': policies,
    }
    
    return render(request, 'hr/hr_policies.html', context)

def recruitment_list(request):
    """
    Display all recruitment requests for HR to review
    """
    # Check if user is authorized HR
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get HR user info for header display
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        user_name = hr.staffid.name
        
        # Get all recruitment requests ordered by newest first
        recruitment_requests = RECRUITMENT.objects.select_related(
            'managerid__staffid'
        ).order_by('-id')
        
        # Add pagination if there are many requests
        paginator = Paginator(recruitment_requests, 12)  # Show 12 requests per page
        page_number = request.GET.get('page')
        recruitment_requests = paginator.get_page(page_number)
        
        context = {
            'recruitment_requests': recruitment_requests,
            'user_name': user_name,
            'total_requests': RECRUITMENT.objects.count(),
            'hr':hr,
        }
        
        return render(request, 'hr/recruitment.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hrmenu')

def recruitment_details(request, request_id):
    """
    Display detailed view of a specific recruitment request
    """
    # Check if user is authorized HR
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get HR user info
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        user_name = hr.staffid.name
        
        # Get the specific recruitment request
        recruitment_request = get_object_or_404(
            RECRUITMENT.objects.select_related('managerid__staffid'),
            id=request_id
        )
        
        context = {
            'recruitment_request': recruitment_request,
            'user_name': user_name,
            'manager_name': recruitment_request.managerid.staffid.name,
            'manager_position': recruitment_request.managerid.staffid.position,
            'manager_email': recruitment_request.managerid.staffid.email,
            'manager_phone': recruitment_request.managerid.staffid.phone,
            'hr': hr,
        }
        
        return render(request, 'hr/recruitment_details.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')

def recruitment_process(request, request_id):
    """
    Process a recruitment request (mark as processed, add notes, etc.)
    """
    # Check if user is authorized HR
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get the recruitment request
        recruitment_request = get_object_or_404(RECRUITMENT, id=request_id)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'acknowledge':
                # Mark as acknowledged/processed
                messages.success(request, f"Recruitment request for {recruitment_request.position} has been acknowledged and will be processed.")
                return redirect('hr_recruitment')
            
            elif action == 'delete':
                # Delete the request (if needed)
                position = recruitment_request.position
                recruitment_request.delete()
                messages.success(request, f"Recruitment request for {position} has been removed.")
                return redirect('hr_recruitment')
        
        # Get HR user info
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        user_name = hr.staffid.name
        
        context = {
            'recruitment_request': recruitment_request,
            'user_name': user_name,
            'hr':hr,
        }
        
        return render(request, 'hr/recruitment_process.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')

def recruitment_search(request):
    """
    Search and filter recruitment requests
    """
    # Check if user is authorized HR
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get HR user info
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        user_name = hr.staffid.name
        
        # Get search parameters
        search_query = request.GET.get('search', '')
        position_filter = request.GET.get('position', '')
        manager_filter = request.GET.get('manager', '')
        
        # Start with all recruitment requests
        recruitment_requests = RECRUITMENT.objects.select_related('managerid__staffid')
        
        # Apply filters
        if search_query:
            recruitment_requests = recruitment_requests.filter(
                Q(position__icontains=search_query) |
                Q(reason__icontains=search_query) |
                Q(managerid__staffid__name__icontains=search_query)
            )
        
        if position_filter:
            recruitment_requests = recruitment_requests.filter(position__icontains=position_filter)
        
        if manager_filter:
            recruitment_requests = recruitment_requests.filter(managerid__staffid__name__icontains=manager_filter)
        
        recruitment_requests = recruitment_requests.order_by('-id')
        
        # Get unique positions and managers for filter options
        all_positions = RECRUITMENT.objects.values_list('position', flat=True).distinct()
        all_managers = RECRUITMENT.objects.select_related('managerid__staffid').values_list('managerid__staffid__name', flat=True).distinct()
        
        context = {
            'recruitment_requests': recruitment_requests,
            'user_name': user_name,
            'search_query': search_query,
            'position_filter': position_filter,
            'manager_filter': manager_filter,
            'all_positions': all_positions,
            'all_managers': all_managers,
            'hr':hr,
        }
        
        return render(request, 'hr/recruitment_search.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')

def hr_feedback(request):
    # Check if user is HR
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    # Get HR information for header display
    hr_id = request.session.get('user_id')
    try:
        hr = HR.objects.get(id=hr_id)
        hr_name = hr.staffid.name
        hr_position = hr.staffid.position
    except HR.DoesNotExist:
        messages.error(request, "HR profile not found. Please login again.")
        return redirect('login')
    
    # Get all feedback, separated by status
    unsolved_feedback = FEEDBACK.objects.filter(status='Unsolved').order_by('-id')
    solved_feedback = FEEDBACK.objects.filter(status='Solved').order_by('-id')
    
    # Filter complaints specifically
    unsolved_complaints = unsolved_feedback.filter(category='Complaint')
    solved_complaints = solved_feedback.filter(category='Complaint')
    
    # Get all feedback (both complaints and feedback)
    all_unsolved = unsolved_feedback
    all_solved = solved_feedback
    
    context = {
        'hr_name': hr_name,
        'hr_position': hr_position,
        'unsolved_feedback': all_unsolved,
        'solved_feedback': all_solved,
        'unsolved_complaints': unsolved_complaints,
        'solved_complaints': solved_complaints,
        'unsolved_count': all_unsolved.count(),
        'solved_count': all_solved.count(),
    }
    
    return render(request, 'hr/feedback.html', context)

def update_feedback_status(request):
    # Check if user is HR
    if not request.session.get('user_type') == 'hr':
        return JsonResponse({'success': False, 'message': 'Unauthorized access'})
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            feedback_id = data.get('feedback_id')
            new_status = data.get('status')
            
            # Validate status
            if new_status not in ['Unsolved', 'Solved']:
                return JsonResponse({'success': False, 'message': 'Invalid status'})
            
            # Get and update feedback
            feedback = get_object_or_404(FEEDBACK, id=feedback_id)
            feedback.status = new_status
            feedback.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'Feedback status updated to {new_status}',
                'new_status': new_status
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


# manager

def managermenu(request):
    # Check if user is authenticated and is a manager
    if not request.session.get('user_type') == 'manager':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    # Get manager information
    manager_id = request.session.get('user_id')
    
    manager = MANAGER.objects.get(id=manager_id)
    context = {
        'manager': manager
    }
    return render(request, 'manager/managermenu.html', context)
    