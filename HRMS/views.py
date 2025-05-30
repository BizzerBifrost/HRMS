# Add this to the top of your HRMSKPMIM/HRMS/views.py file
# Update your existing imports to include TEAM_GOALS:

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from .models import (
    STAFF, EDUCATION, EXPERIENCE, ADDRESS, PAYROLL, 
    FEEDBACK, LEAVE_BALANCE, TIMEOFF, MANAGER, 
    RECRUITMENT, TEAM, TEAM_MEMBERSHIP, HR, POLICIES, ADMIN, TEAM_GOALS
)
import logging
import secrets
import hashlib
from django.http import HttpResponse, Http404
from django.urls import reverse
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
from django.utils import timezone
import pytz
from datetime import datetime, date
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
            user = STAFF.objects.get(id=user_id)
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
                geng = TEAM.objects.get(managerid=managers)
                team_member = TEAM_MEMBERSHIP(
                    staff = staff,
                    team = geng,
                )
                team_member.save()
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
                messages.success(request, f'Manager {staff.name} added successfully')
                managers = MANAGER.objects.get(id=user_id)
                team = TEAM(
                    managerid = managers,
                )
                team.save()
                geng = TEAM.objects.get(managerid=managers)
                team_member = TEAM_MEMBERSHIP(
                    staff = staff,
                    team = geng,
                )
                team_member.save()
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
                messages.success(request, f'HR {staff.name} added successfully')
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
    
    # Get or create leave balance for this staff member
    leave_balance, created = LEAVE_BALANCE.objects.get_or_create(staffid=staff)
    if created:
        # If newly created, ensure it has default values
        leave_balance.annual_leave = 14
        leave_balance.leave_available = 14
        leave_balance.save()
    
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name', '').strip()
        position = request.POST.get('position', '').strip()
        gender = request.POST.get('gender', '')
        annual_leave = request.POST.get('annual_leave', '').strip()
        
        # Password handling
        new_password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        try:
            # Update staff information
            staff.name = name
            staff.position = position
            staff.gender = gender
            
            # Handle annual leave update
            if annual_leave:
                try:
                    annual_leave_int = int(annual_leave)
                    if annual_leave_int < 0:
                        messages.error(request, 'Annual leave cannot be negative.')
                        hr_id = request.session.get('user_id')
                        hr = HR.objects.get(id=hr_id)
                        return render(request, 'hr/update_staff.html', {
                            'staff': staff, 
                            'hr': hr, 
                            'leave_balance': leave_balance
                        })
                    
                    # Calculate the difference to adjust leave_available accordingly
                    old_annual_leave = leave_balance.annual_leave
                    leave_difference = annual_leave_int - old_annual_leave
                    
                    # Update annual leave
                    leave_balance.annual_leave = annual_leave_int
                    
                    # Adjust available leave proportionally
                    # If annual leave increased, add the difference to available leave
                    # If annual leave decreased, subtract the difference from available leave
                    leave_balance.leave_available += leave_difference
                    
                    # Ensure leave_available doesn't go below 0
                    if leave_balance.leave_available < 0:
                        leave_balance.leave_available = 0
                    
                    # Ensure leave_available doesn't exceed annual_leave
                    if leave_balance.leave_available > leave_balance.annual_leave:
                        leave_balance.leave_available = leave_balance.annual_leave
                    
                    leave_balance.save()
                    
                except ValueError:
                    messages.error(request, 'Please enter a valid number for annual leave.')
                    hr_id = request.session.get('user_id')
                    hr = HR.objects.get(id=hr_id)
                    return render(request, 'hr/update_staff.html', {
                        'staff': staff, 
                        'hr': hr, 
                        'leave_balance': leave_balance
                    })
            
            staff.save()
            
            messages.success(request, f'Staff {staff.name} has been updated successfully.')
            return redirect('employee_management')
            
        except Exception as e:
            messages.error(request, f'Error updating staff: {str(e)}')
            hr_id = request.session.get('user_id')
            hr = HR.objects.get(id=hr_id)
            return render(request, 'hr/update_staff.html', {
                'staff': staff, 
                'hr': hr, 
                'leave_balance': leave_balance
            })
    
    # GET request - display the form
    hr_id = request.session.get('user_id')
    hr = HR.objects.get(id=hr_id)
    
    context = {
        'staff': staff,
        'hr': hr,
        'leave_balance': leave_balance
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
    
# Add these functions to your HRMS/views.py file

def leave_approvals(request):
    """View for managers to see and approve/deny leave requests from their team"""
    # Check if user is authenticated and is a manager
    if not request.session.get('user_type') == 'manager':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get manager information
        manager_id = request.session.get('user_id')
        manager = MANAGER.objects.get(id=manager_id)
        
        # Get team members for this manager
        team = TEAM.objects.get(managerid=manager)
        team_members = TEAM_MEMBERSHIP.objects.filter(team=team).select_related('staff')
        team_staff_ids = [member.staff.id for member in team_members]
        
        # Get all leave requests from team members
        leave_requests = TIMEOFF.objects.filter(
            staffid__id__in=team_staff_ids
        ).select_related('staffid').order_by('-id')
        
        # Separate pending and processed requests
        pending_requests = leave_requests.filter(status='Pending')
        processed_requests = leave_requests.exclude(status='Pending')
        
        context = {
            'manager': manager,
            'pending_requests': pending_requests,
            'processed_requests': processed_requests,
            'pending_count': pending_requests.count(),
            'processed_count': processed_requests.count(),
        }
        
        return render(request, 'manager/leave_approvals.html', context)
        
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('managermenu')

def process_leave_request(request):
    """Process leave approval/denial"""
    # Check if user is authenticated and is a manager
    if not request.session.get('user_type') == 'manager':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    if request.method == 'POST':
        try:
            # Get manager information
            manager_id = request.session.get('user_id')
            manager = MANAGER.objects.get(id=manager_id)
            
            # Get form data
            request_id = request.POST.get('request_id')
            action = request.POST.get('action')  # 'approve' or 'deny'
            
            # Get the leave request
            leave_request = get_object_or_404(TIMEOFF, id=request_id)
            
            # Verify that this staff member is under this manager's team
            team = TEAM.objects.get(managerid=manager)
            team_members = TEAM_MEMBERSHIP.objects.filter(team=team).select_related('staff')
            team_staff_ids = [member.staff.id for member in team_members]
            
            if leave_request.staffid.id not in team_staff_ids:
                messages.error(request, "You can only process leave requests from your team members.")
                return redirect('leave_approvals')
            
            # Check if request is still pending
            if leave_request.status != 'Pending':
                messages.error(request, "This leave request has already been processed.")
                return redirect('leave_approvals')
            
            # Process the request
            if action == 'approve':
                # Check if staff has enough leave balance
                leave_balance, created = LEAVE_BALANCE.objects.get_or_create(staffid=leave_request.staffid)
                
                if leave_balance.leave_available < leave_request.total_days:
                    messages.error(request, f"Cannot approve leave. {leave_request.staffid.name} only has {leave_balance.leave_available} days available, but requested {leave_request.total_days} days.")
                    return redirect('leave_approvals')
                
                leave_request.status = 'Approved'
                leave_request.save()
                messages.success(request, f"Leave request for {leave_request.staffid.name} has been approved.")
                
            elif action == 'deny':
                leave_request.status = 'Denied'
                leave_request.save()
                messages.success(request, f"Leave request for {leave_request.staffid.name} has been denied.")
            
            else:
                messages.error(request, "Invalid action specified.")
            
            return redirect('leave_approvals')
            
        except MANAGER.DoesNotExist:
            messages.error(request, "Manager profile not found. Please login again.")
            return redirect('login')
        except TEAM.DoesNotExist:
            messages.error(request, "No team assigned to this manager.")
            return redirect('managermenu')
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('leave_approvals')
    
    return redirect('leave_approvals')

def get_malaysia_date():
    """Get current date in Malaysia timezone"""
    malaysia_tz = pytz.timezone('Asia/Kuala_Lumpur')
    return timezone.now().astimezone(malaysia_tz).date()

# Update the relevant parts of your team_goals view:
def team_goals(request):
    """View for managers to create, edit, and manage team goals using TEAM_GOALS model"""
    # ... existing code ...
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_goal':
            # ... existing validation code ...
            
            # Check if target date is not in the past (using Malaysia time)
            malaysia_today = get_malaysia_date()
            if target_date_parsed < malaysia_today:
                messages.error(request, 'Target date cannot be in the past.')
                return redirect('team_goals')
            
    
    # Check if user is authenticated and is a manager
    if not request.session.get('user_type') == 'manager':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get manager information
        manager_id = request.session.get('user_id')
        manager = MANAGER.objects.get(id=manager_id)
        
        # Get the team for this manager
        team = TEAM.objects.get(managerid=manager)
        
        # Get team members
        team_members = TEAM_MEMBERSHIP.objects.filter(team=team).select_related('staff')
        
        # Check if we're editing a goal
        editing_goal_id = request.GET.get('edit')
        editing_goal = None
        if editing_goal_id:
            try:
                editing_goal = TEAM_GOALS.objects.get(id=editing_goal_id, team=team)
            except TEAM_GOALS.DoesNotExist:
                messages.error(request, "Goal not found.")
                return redirect('team_goals')
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'add_goal':
                # Create new goal
                title = request.POST.get('title', '').strip()
                description = request.POST.get('description', '').strip()
                target_date = request.POST.get('target_date')
                priority = request.POST.get('priority')
                
                if title and description and target_date and priority:
                    try:
                        # Parse target date
                        target_date_parsed = parse_date(target_date)
                        
                        if not target_date_parsed:
                            messages.error(request, 'Invalid target date format.')
                            return redirect('team_goals')
                        
                        # Check if target date is not in the past
                        if target_date_parsed < timezone.now().date():
                            messages.error(request, 'Target date cannot be in the past.')
                            return redirect('team_goals')
                        
                        # Create the goal
                        goal = TEAM_GOALS.objects.create(
                            title=title,
                            description=description,
                            target_date=target_date_parsed,
                            priority=priority,
                            team=team,
                            created_by=manager,
                            status='Not Started',
                            progress_percentage=0
                        )
                        
                        messages.success(request, f'Goal "{title}" has been created successfully!')
                        return redirect('team_goals')
                        
                    except Exception as e:
                        messages.error(request, f'Error creating goal: {str(e)}')
                else:
                    messages.error(request, 'All fields are required to create a goal.')
            
            elif action == 'edit_goal':
                # Edit existing goal
                goal_id = request.POST.get('goal_id')
                title = request.POST.get('title', '').strip()
                description = request.POST.get('description', '').strip()
                target_date = request.POST.get('target_date')
                priority = request.POST.get('priority')
                status = request.POST.get('status')
                progress_percentage = request.POST.get('progress_percentage', '0')
                notes = request.POST.get('notes', '').strip()
                
                if goal_id and title and description and target_date and priority and status:
                    try:
                        goal = TEAM_GOALS.objects.get(id=goal_id, team=team)
                        
                        # Parse target date
                        target_date_parsed = parse_date(target_date)
                        
                        if not target_date_parsed:
                            messages.error(request, 'Invalid target date format.')
                            return redirect('team_goals')
                        
                        # Parse progress percentage
                        try:
                            progress_int = int(progress_percentage)
                            if progress_int < 0 or progress_int > 100:
                                messages.error(request, 'Progress percentage must be between 0 and 100.')
                                return redirect('team_goals')
                        except ValueError:
                            progress_int = 0
                        
                        # Update the goal
                        goal.title = title
                        goal.description = description
                        goal.target_date = target_date_parsed
                        goal.priority = priority
                        goal.status = status
                        goal.progress_percentage = progress_int
                        goal.notes = notes
                        goal.save()
                        
                        messages.success(request, f'Goal "{title}" has been updated successfully!')
                        return redirect('team_goals')
                        
                    except TEAM_GOALS.DoesNotExist:
                        messages.error(request, 'Goal not found.')
                    except Exception as e:
                        messages.error(request, f'Error updating goal: {str(e)}')
                else:
                    messages.error(request, 'All required fields must be filled to update the goal.')
            
            elif action == 'delete_goal':
                # Delete goal
                goal_id = request.POST.get('goal_id')
                
                if goal_id:
                    try:
                        goal = TEAM_GOALS.objects.get(id=goal_id, team=team)
                        goal_title = goal.title
                        goal.delete()
                        
                        messages.success(request, f'Goal "{goal_title}" has been deleted successfully!')
                        return redirect('team_goals')
                        
                    except TEAM_GOALS.DoesNotExist:
                        messages.error(request, 'Goal not found.')
                    except Exception as e:
                        messages.error(request, f'Error deleting goal: {str(e)}')
                else:
                    messages.error(request, 'Invalid goal ID.')
            
            return redirect('team_goals')
        
        # GET request - display the goals management page
        # Get all goals for this team ordered by most recent first
        goals = TEAM_GOALS.objects.filter(team=team).order_by('-created_date')
        
        # In the context, use Malaysia time for today's date
        context = {
            'manager': manager,
            'team': team,
            'team_members': team_members,
            'goals': goals,
            'editing_goal': editing_goal,
            'today': get_malaysia_date(),  # Use Malaysia date
        } 
        
        return render(request, 'manager/team_goals.html', context)
    
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('managermenu')
    
# Add this function to your HRMS/views.py file

def recruitment_request(request):
    """
    View for managers to submit recruitment requests
    """
    # Check if user is authenticated and is a manager
    if not request.session.get('user_type') == 'manager':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get manager information
        manager_id = request.session.get('user_id')
        manager = MANAGER.objects.get(id=manager_id)
        
        if request.method == 'POST':
            # Get form data
            position = request.POST.get('position', '').strip()
            total_personnel_str = request.POST.get('total_personnel', '').strip()
            reason = request.POST.get('reason', '').strip()
            
            # Validate required fields
            if not position or not total_personnel_str or not reason:
                messages.error(request, 'All fields are required.')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
            
            # Validate total personnel
            try:
                total_personnel = int(total_personnel_str)
                if total_personnel < 1 or total_personnel > 10:
                    messages.error(request, 'Number of personnel must be between 1 and 10.')
                    return render(request, 'manager/recruitment_request.html', {
                        'manager': manager
                    })
            except ValueError:
                messages.error(request, 'Please enter a valid number for personnel needed.')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
            
            # Validate reason length
            if len(reason) > 1000:
                messages.error(request, 'Justification is too long (maximum 1000 characters).')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
            
            # Validate position title
            if len(position) > 100:
                messages.error(request, 'Position title is too long (maximum 100 characters).')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
            
            try:
                # Create the recruitment request
                recruitment_request = RECRUITMENT.objects.create(
                    position=position,
                    reason=reason,
                    total_personnel=total_personnel,
                    managerid=manager
                )
                
                # Success message with details
                personnel_text = "person" if total_personnel == 1 else "people"
                success_message = f'Recruitment request submitted successfully! Request for {total_personnel} {personnel_text} for {position} position has been sent to HR for review.'
                messages.success(request, success_message)
                
                # Redirect to prevent form resubmission
                return redirect('managermenu')
                
            except Exception as e:
                messages.error(request, f'Error submitting recruitment request: {str(e)}')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
        
        # GET request - show the form
        context = {
            'manager': manager
        }
        
        return render(request, 'manager/recruitment_request.html', context)
    
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('managermenu')

# staff

def staffmenu(request):
    # Check if user is authenticated and is staff
    if not request.session.get('user_type') == 'staff':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    # Get staff information
    staff_id = request.session.get('user_id')
    
    try:
        staff = STAFF.objects.get(id=staff_id)
        context = {
            'staff': staff
        }
        return render(request, 'staff/staffmenu.html', context)
    
    except Exception as e:
        # Handle any other exceptions
        request.session.flush()
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('login')
    
def staff_leave_application(request):
    # Check if user is authenticated and is staff
    if not request.session.get('user_type') == 'staff':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    # Get staff information
    staff_id = request.session.get('user_id')
    
    try:
        staff = STAFF.objects.get(id=staff_id)
        
        # Get or create leave balance for the staff
        leave_balance, created = LEAVE_BALANCE.objects.get_or_create(
            staffid=staff,
            defaults={
                'annual_leave': 14,
                'leave_available': 14,
                'year': timezone.now().year
            }
        )
        
        # Update leave balance to ensure it's current
        leave_balance.update_leave_available()
        
        if request.method == 'POST':
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            reason = request.POST.get('reason', '').strip()
            
            # Validate input
            if not start_date_str or not end_date_str or not reason:
                messages.error(request, 'All fields are required.')
                return render(request, 'staff/leave_application.html', {
                    'staff': staff,
                    'leave_balance': leave_balance,
                    'today': timezone.now().date()
                })
            
            try:
                # Parse dates
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                
                if not start_date or not end_date:
                    messages.error(request, 'Invalid date format.')
                    return render(request, 'staff/leave_application.html', {
                        'staff': staff,
                        'leave_balance': leave_balance,
                        'today': timezone.now().date()
                    })
                
                # Validate date logic
                if start_date > end_date:
                    messages.error(request, 'Start date cannot be after end date.')
                    return render(request, 'staff/leave_application.html', {
                        'staff': staff,
                        'leave_balance': leave_balance,
                        'today': timezone.now().date()
                    })
                
                # Check if start date is not in the past
                if start_date < timezone.now().date():
                    messages.error(request, 'Leave application cannot be for past dates.')
                    return render(request, 'staff/leave_application.html', {
                        'staff': staff,
                        'leave_balance': leave_balance,
                        'today': timezone.now().date()
                    })
                
                # Calculate total days
                total_days = (end_date - start_date).days + 1
                
                # Check if staff has enough leave balance
                if total_days > leave_balance.leave_available:
                    messages.error(request, f'Insufficient leave balance. You have {leave_balance.leave_available} days available, but requested {total_days} days.')
                    return render(request, 'staff/leave_application.html', {
                        'staff': staff,
                        'leave_balance': leave_balance,
                        'today': timezone.now().date()
                    })
                
                # Check for overlapping leave applications
                overlapping_leaves = TIMEOFF.objects.filter(
                    staffid=staff,
                    status__in=['Pending', 'Approved']
                ).filter(
                    Q(start__lte=end_date) & Q(end__gte=start_date)
                )
                
                if overlapping_leaves.exists():
                    messages.error(request, 'You already have a leave application for the selected date range.')
                    return render(request, 'staff/leave_application.html', {
                        'staff': staff,
                        'leave_balance': leave_balance,
                        'today': timezone.now().date()
                    })
                
                # Create the leave application
                leave_application = TIMEOFF.objects.create(
                    staffid=staff,
                    start=start_date,
                    end=end_date,
                    reason=reason,
                    status='Pending'
                )
                
                messages.success(request, f'Leave application submitted successfully! Your application for {total_days} day(s) from {start_date.strftime("%B %d, %Y")} to {end_date.strftime("%B %d, %Y")} is now pending approval.')
                return redirect('staff_leave_status')  # Redirect to leave status page
                
            except ValueError as e:
                messages.error(request, f'Invalid date provided: {str(e)}')
                return render(request, 'staff/leave_application.html', {
                    'staff': staff,
                    'leave_balance': leave_balance,
                    'today': timezone.now().date()
                })
            except Exception as e:
                messages.error(request, f'An error occurred while processing your application: {str(e)}')
                return render(request, 'staff/leave_application.html', {
                    'staff': staff,
                    'leave_balance': leave_balance,
                    'today': timezone.now().date()
                })
        
        # GET request - show the form
        context = {
            'staff': staff,
            'leave_balance': leave_balance,
            'today': timezone.now().date()
        }
        
        return render(request, 'staff/leave_application.html', context)
        
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('staffmenu')

def staff_leave_status(request):
    # Check if user is authenticated and is staff
    if not request.session.get('user_type') == 'staff':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    # Get staff information
    staff_id = request.session.get('user_id')
    
    try:
        staff = STAFF.objects.get(id=staff_id)
        
        # Get all leave applications for this staff, ordered by most recent first
        leave_applications = TIMEOFF.objects.filter(staffid=staff).order_by('-id')
        
        # Get leave balance
        leave_balance, created = LEAVE_BALANCE.objects.get_or_create(
            staffid=staff,
            defaults={
                'annual_leave': 14,
                'leave_available': 14,
                'year': timezone.now().year
            }
        )
        
        # Update leave balance to ensure it's current
        leave_balance.update_leave_available()
        
        context = {
            'staff': staff,
            'leave_applications': leave_applications,
            'leave_balance': leave_balance,
        }
        
        return render(request, 'staff/leave_status.html', context)
        
    
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('staffmenu')
    
def team_management(request):
    """View for managers to manage their team members and team information"""
    # Check if user is authenticated and is a manager
    if not request.session.get('user_type') == 'manager':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get manager information
        manager_id = request.session.get('user_id')
        manager = MANAGER.objects.get(id=manager_id)
        
        # Get or create team for this manager
        team, created = TEAM.objects.get_or_create(
            managerid=manager,
            defaults={
                'name': f"{manager.staffid.name}'s Team",
            }
        )
        
        # Handle POST requests for team management actions
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'edit_team':
                # Update team information
                team_name = request.POST.get('team_name', '').strip()
                
                
                if team_name:
                    team.name = team_name
                    
                    team.save()
                    messages.success(request, 'Team information updated successfully!')
                else:
                    messages.error(request, 'Team name is required.')
                
                return redirect('team_management')
            
            elif action == 'add_member':
                # Add new team member
                staff_id = request.POST.get('staff_id', '').strip()
                
                if not staff_id:
                    messages.error(request, 'Staff ID is required.')
                    return redirect('team_management')
                
                try:
                    # Check if staff exists
                    staff = STAFF.objects.get(id=staff_id)
                    
                    # Check if staff is already a member of this team
                    existing_membership = TEAM_MEMBERSHIP.objects.filter(
                        team=team, 
                        staff=staff
                    ).first()
                    
                    if existing_membership:
                        messages.error(request, f'{staff.name} is already a member of this team.')
                        return redirect('team_management')
                    
                    # Check if staff is already a member of another team
                    other_membership = TEAM_MEMBERSHIP.objects.filter(staff=staff).first()
                    if other_membership:
                        messages.error(request, f'{staff.name} is already a member of {other_membership.team.name}.')
                        return redirect('team_management')
                    
                    # Check if the staff is the manager themselves
                    if staff.id == manager.staffid.id:
                        messages.error(request, 'You cannot add yourself as a team member.')
                        return redirect('team_management')
                    
                    # Add staff to team
                    TEAM_MEMBERSHIP.objects.create(
                        team=team,
                        staff=staff
                    )
                    
                    messages.success(request, f'{staff.name} has been added to the team successfully!')
                    
                except STAFF.DoesNotExist:
                    messages.error(request, f'Staff with ID {staff_id} not found.')
                except Exception as e:
                    messages.error(request, f'Error adding team member: {str(e)}')
                
                return redirect('team_management')
            
            elif action == 'remove_member':
                # Remove team member
                staff_id = request.POST.get('staff_id', '').strip()
                
                if not staff_id:
                    messages.error(request, 'Staff ID is required.')
                    return redirect('team_management')
                
                try:
                    staff = STAFF.objects.get(id=staff_id)
                    membership = TEAM_MEMBERSHIP.objects.get(team=team, staff=staff)
                    
                    membership.delete()
                    messages.success(request, f'{staff.name} has been removed from the team.')
                    
                except STAFF.DoesNotExist:
                    messages.error(request, f'Staff with ID {staff_id} not found.')
                except TEAM_MEMBERSHIP.DoesNotExist:
                    messages.error(request, f'Staff is not a member of this team.')
                except Exception as e:
                    messages.error(request, f'Error removing team member: {str(e)}')
                
                return redirect('team_management')
        
        # GET request - display team management page
        # Get all team members
        team_members = TEAM_MEMBERSHIP.objects.filter(team=team).select_related('staff').order_by('staff__name')
        
        context = {
            'manager': manager,
            'team': team,
            'team_members': team_members,
        }
        
        return render(request, 'manager/team_management.html', context)
        
    except MANAGER.DoesNotExist:
        messages.error(request, "Manager profile not found. Please login again.")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('managermenu')
    
def staff_view_goals(request):
    """View for staff to view team goals set by their manager"""
    # Check if user is authenticated and is staff
    if not request.session.get('user_type') == 'staff':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get staff information
        staff_id = request.session.get('user_id')
        staff = STAFF.objects.get(id=staff_id)
        
        # Find which team this staff member belongs to
        try:
            team_membership = TEAM_MEMBERSHIP.objects.get(staff=staff)
            team = team_membership.team
            
            # Get all goals for this team ordered by priority and target date
            goals = TEAM_GOALS.objects.filter(team=team).order_by('target_date', '-priority')
            
            # Separate goals by status for better organization
            active_goals = goals.exclude(status='Completed')
            completed_goals = goals.filter(status='Completed')
            
        except TEAM_MEMBERSHIP.DoesNotExist:
            # Staff is not assigned to any team
            team = None
            goals = None
            active_goals = None
            completed_goals = None
        
        context = {
            'staff': staff,
            'team': team,
            'goals': goals,
            'active_goals': active_goals,
            'completed_goals': completed_goals,
        }
        
        return render(request, 'staff/view_goals.html', context)
        
    except STAFF.DoesNotExist:
        messages.error(request, "Staff profile not found. Please login again.")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('staffmenu')
      
