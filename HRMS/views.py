# Add this to the top of your HRMSKPMIM/HRMS/views.py fileSTATUS_HISTORY
# Update your existing imports to include TEAM_GOALS:

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from .models import (
    STAFF, EDUCATION, EXPERIENCE, ADDRESS, PAYROLL, 
    FEEDBACK, LEAVE_BALANCE, TIMEOFF, MANAGER, 
    RECRUITMENT,RECRUITMENT_NOTES,RECRUITMENT_STATUS_HISTORY,RECRUITMENT_ATTACHMENTS, TEAM, TEAM_MEMBERSHIP, HR, POLICIES, ADMIN, TEAM_GOALS
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
from decimal import Decimal, InvalidOperation
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
import json
import io
from django.db.models import Count, Avg, Q, Sum, Case, When, F, IntegerField
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
import xlsxwriter
from django.core.mail import send_mail
from django.conf import settings
import uuid
from threading import Timer
import os
from dateutil.relativedelta import relativedelta


# Create your views here.
def get_malaysia_time():
    """Get current time in Malaysia timezone"""
    malaysia_tz = pytz.timezone('Asia/Kuala_Lumpur')
    return timezone.now().astimezone(malaysia_tz)

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

# Updated recruitment views for HRMS/views.py
# Replace the existing recruitment functions with these improved versions

def recruitment_list(request):
    """
    Display recruitment dashboard with statistics and recent requests
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
        
        # Calculate statistics
        total_requests = RECRUITMENT.objects.count()
        pending_count = RECRUITMENT.objects.filter(status='Pending').count()
        in_progress_count = RECRUITMENT.objects.filter(status__in=['Under Review', 'In Progress', 'Approved']).count()
        completed_count = RECRUITMENT.objects.filter(status='Completed').count()
        urgent_count = RECRUITMENT.objects.filter(priority__in=['Urgent', 'Critical']).count()
        
        # Get recent requests (last 10)
        recruitment_requests = RECRUITMENT.objects.select_related(
            'managerid__staffid'
        ).order_by('-requested_date')[:10]
        
        # Add pagination for the recent requests display
        paginator = Paginator(recruitment_requests, 10)  
        page_number = request.GET.get('page', 1)
        recruitment_requests = paginator.get_page(page_number)
        
        context = {
            'hr': hr,
            'recruitment_requests': recruitment_requests,
            'total_requests': total_requests,
            'pending_count': pending_count,
            'in_progress_count': in_progress_count,
            'completed_count': completed_count,
            'urgent_count': urgent_count,
        }
        
        return render(request, 'hr/recruitment.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hrmenu')

def recruitment_search(request):
    """
    Advanced search and filter page for recruitment requests
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
        
        # Get search parameters from request
        search_query = request.GET.get('search', '').strip()
        status_filter = request.GET.get('status', '')
        priority_filter = request.GET.get('priority', '')
        position_filter = request.GET.get('position', '').strip()
        manager_filter = request.GET.get('manager', '').strip()
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        personnel_min = request.GET.get('personnel_min', '')
        sort_by = request.GET.get('sort', 'newest')
        page_size = int(request.GET.get('page_size', 25))
        
        # Start with all recruitment requests
        recruitment_requests = RECRUITMENT.objects.select_related('managerid__staffid')
        
        # Track if any search was performed
        search_performed = any([
            search_query, status_filter, priority_filter, position_filter,
            manager_filter, date_from, date_to, personnel_min
        ])
        
        # Apply filters
        if search_query:
            recruitment_requests = recruitment_requests.filter(
                Q(position__icontains=search_query) |
                Q(reason__icontains=search_query) |
                Q(business_justification__icontains=search_query) |
                Q(managerid__staffid__name__icontains=search_query)
            )
        
        if status_filter:
            recruitment_requests = recruitment_requests.filter(status=status_filter)
        
        if priority_filter:
            recruitment_requests = recruitment_requests.filter(priority=priority_filter)
        
        if position_filter:
            recruitment_requests = recruitment_requests.filter(position__icontains=position_filter)
        
        if manager_filter:
            recruitment_requests = recruitment_requests.filter(
                managerid__staffid__name__icontains=manager_filter
            )
        
        if date_from:
            try:
                from_date = parse_date(date_from)
                if from_date:
                    recruitment_requests = recruitment_requests.filter(requested_date__date__gte=from_date)
            except:
                messages.warning(request, 'Invalid "from" date format.')
        
        if date_to:
            try:
                to_date = parse_date(date_to)
                if to_date:
                    recruitment_requests = recruitment_requests.filter(requested_date__date__lte=to_date)
            except:
                messages.warning(request, 'Invalid "to" date format.')
        
        if personnel_min:
            try:
                min_personnel = int(personnel_min)
                recruitment_requests = recruitment_requests.filter(total_personnel__gte=min_personnel)
            except ValueError:
                messages.warning(request, 'Invalid minimum personnel value.')
        
        # Apply sorting
        if sort_by == 'oldest':
            recruitment_requests = recruitment_requests.order_by('requested_date')
        elif sort_by == 'priority':
            # Custom ordering: Critical, Urgent, High, Standard, Low
            priority_order = ['Critical', 'Urgent', 'High', 'Standard', 'Low']
            recruitment_requests = recruitment_requests.extra(
                select={
                    'priority_order': 
                    "CASE "
                    "WHEN priority = 'Critical' THEN 1 "
                    "WHEN priority = 'Urgent' THEN 2 "
                    "WHEN priority = 'High' THEN 3 "
                    "WHEN priority = 'Standard' THEN 4 "
                    "WHEN priority = 'Low' THEN 5 "
                    "ELSE 6 END"
                }
            ).order_by('priority_order', '-requested_date')
        elif sort_by == 'status':
            recruitment_requests = recruitment_requests.order_by('status', '-requested_date')
        elif sort_by == 'position':
            recruitment_requests = recruitment_requests.order_by('position')
        else:  # newest (default)
            recruitment_requests = recruitment_requests.order_by('-requested_date')
        
        # Get total count before pagination
        total_results = recruitment_requests.count()
        
        # Apply pagination
        paginator = Paginator(recruitment_requests, page_size)
        page_number = request.GET.get('page', 1)
        recruitment_requests = paginator.get_page(page_number)
        
        # Get filter options for dropdowns (for advanced filtering in future)
        all_statuses = RECRUITMENT.objects.values_list('status', flat=True).distinct()
        all_priorities = RECRUITMENT.objects.values_list('priority', flat=True).distinct()
        all_positions = RECRUITMENT.objects.values_list('position', flat=True).distinct()
        all_managers = RECRUITMENT.objects.select_related('managerid__staffid').values_list(
            'managerid__staffid__name', flat=True
        ).distinct()
        
        context = {
            'hr': hr,
            'recruitment_requests': recruitment_requests,
            'total_results': total_results,
            'search_performed': search_performed,
            
            # Search parameters (to maintain form state)
            'search_query': search_query,
            'status_filter': status_filter,
            'priority_filter': priority_filter,
            'position_filter': position_filter,
            'manager_filter': manager_filter,
            'date_from': date_from,
            'date_to': date_to,
            'personnel_min': personnel_min,
            'sort_by': sort_by,
            'page_size': page_size,
            
            # Filter options for dropdowns
            'all_statuses': all_statuses,
            'all_priorities': all_priorities,
            'all_positions': all_positions,
            'all_managers': all_managers,
        }
        
        return render(request, 'hr/recruitment_search.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')

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
        
        # Get the specific recruitment request
        recruitment_request = get_object_or_404(
            RECRUITMENT.objects.select_related('managerid__staffid'),
            id=request_id
        )
        
        context = {
            'recruitment_request': recruitment_request,
            'hr': hr,
            'manager_name': recruitment_request.managerid.staffid.name,
            'manager_position': recruitment_request.managerid.staffid.position,
            'manager_email': recruitment_request.managerid.staffid.email,
            'manager_phone': recruitment_request.managerid.staffid.phone,
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
            
            if action == 'update_status':
                new_status = request.POST.get('status')
                if new_status in dict(RECRUITMENT.STATUS_CHOICES):
                    old_status = recruitment_request.status
                    recruitment_request.status = new_status
                    recruitment_request.save()
                    
                    messages.success(request, f"Status updated from '{old_status}' to '{new_status}' successfully.")
                    return redirect('hr_recruitment_details', request_id=request_id)
                else:
                    messages.error(request, "Invalid status selected.")
            
            elif action == 'acknowledge':
                # Mark as acknowledged/processed
                if recruitment_request.status == 'Pending':
                    recruitment_request.status = 'Under Review'
                    recruitment_request.save()
                
                messages.success(request, f"Recruitment request for {recruitment_request.position} has been acknowledged and is now under review.")
                return redirect('hr_recruitment')
            
            elif action == 'delete':
                # Delete the request (if needed)
                position = recruitment_request.position
                recruitment_request.delete()
                messages.success(request, f"Recruitment request for {position} has been removed.")
                return redirect('hr_recruitment')
            
            elif action == 'assign':
                # Assign to specific HR personnel (placeholder for future implementation)
                messages.info(request, "Assignment functionality will be implemented in future updates.")
                return redirect('hr_recruitment_details', request_id=request_id)
        
        # Get HR user info
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        
        context = {
            'recruitment_request': recruitment_request,
            'hr': hr,
            'status_choices': RECRUITMENT.STATUS_CHOICES,
        }
        
        return render(request, 'hr/recruitment_process.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')
    
def recruitment_notes(request, request_id):
    """
    Manage notes for a specific recruitment request
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
        
        # Get the specific recruitment request
        recruitment_request = get_object_or_404(RECRUITMENT, id=request_id)
        
        # Handle POST requests for note management
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'add_note':
                note_type = request.POST.get('note_type')
                note_content = request.POST.get('note_content', '').strip()
                
                if note_type and note_content:
                    try:
                        # Create new note
                        RECRUITMENT_NOTES.objects.create(
                            recruitment=recruitment_request,
                            note_type=note_type,
                            note_content=note_content,
                            created_by=hr,
                            is_visible_to_manager=False  # Always False since only HR can see notes
                        )
                        messages.success(request, f'Note of type "{note_type}" added successfully!')
                        return redirect('hr_recruitment_notes', request_id=request_id)
                        
                    except Exception as e:
                        messages.error(request, f'Error adding note: {str(e)}')
                else:
                    messages.error(request, 'Note type and content are required.')
            
            elif action == 'edit_note':
                note_id = request.POST.get('note_id')
                note_type = request.POST.get('note_type')
                note_content = request.POST.get('note_content', '').strip()
                
                if note_id and note_type and note_content:
                    try:
                        # Get and update the note
                        note = get_object_or_404(RECRUITMENT_NOTES, id=note_id, recruitment=recruitment_request)
                        note.note_type = note_type
                        note.note_content = note_content
                        note.save()
                        
                        messages.success(request, 'Note updated successfully!')
                        return redirect('hr_recruitment_notes', request_id=request_id)
                    except Exception as e:
                        messages.error(request, f'Error updating note: {str(e)}')
                else:
                    messages.error(request, 'All fields are required for editing.')
            
            elif action == 'delete_note':
                note_id = request.POST.get('note_id')
                
                if note_id:
                    try:
                        # Get and delete the note
                        note = get_object_or_404(RECRUITMENT_NOTES, id=note_id, recruitment=recruitment_request)
                        note.delete()
                        
                        messages.success(request, 'Note deleted successfully!')
                        return redirect('hr_recruitment_notes', request_id=request_id)
                    except Exception as e:
                        messages.error(request, f'Error deleting note: {str(e)}')
                else:
                    messages.error(request, 'Invalid note ID.')
        
        # GET request - display notes page
        notes = RECRUITMENT_NOTES.objects.filter(recruitment=recruitment_request).order_by('-created_date')
        
        # Calculate statistics
        hr_internal_count = notes.filter(note_type='HR Internal').count()
        status_update_count = notes.filter(note_type='Status Update').count()
        interview_note_count = notes.filter(note_type='Interview Note').count()
        general_count = notes.filter(note_type='General').count()
        
        # Get unique note authors
        note_authors = notes.values('created_by__staffid__name').distinct()
        
        context = {
            'hr': hr,
            'recruitment_request': recruitment_request,
            'notes': notes,
            'hr_internal_count': hr_internal_count,
            'status_update_count': status_update_count,
            'interview_note_count': interview_note_count,
            'general_count': general_count,
            'note_authors': note_authors,
        }
        
        return render(request, 'hr/recruitment_notes.html', context)
    
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again.")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')

def recruitment_analytics(request):
    """
    Analytics and reporting dashboard for recruitment data with real calculations
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
        
        # Get time period parameters
        days = int(request.GET.get('days', 30))
        custom_start = request.GET.get('date_from')
        custom_end = request.GET.get('date_to')
        
        # Calculate date range
        if custom_start and custom_end:
            start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
            end_date = datetime.strptime(custom_end, '%Y-%m-%d').date()
            # Convert to datetime for filtering
            start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        else:
            start_datetime = timezone.now() - timedelta(days=days)
            end_datetime = timezone.now()
            start_date = start_datetime.date()
            end_date = end_datetime.date()
        
        # Calculate previous period for comparison
        period_length = (end_datetime - start_datetime).days
        previous_start = start_datetime - timedelta(days=period_length)
        previous_end = start_datetime
        
        # Get recruitment data for current period
        current_requests = RECRUITMENT.objects.filter(
            requested_date__gte=start_datetime,
            requested_date__lte=end_datetime
        ).select_related('managerid__staffid')
        
        # Get recruitment data for previous period
        previous_requests = RECRUITMENT.objects.filter(
            requested_date__gte=previous_start,
            requested_date__lt=previous_end
        ).select_related('managerid__staffid')
        
        # ===== CALCULATE REAL KPIs =====
        
        # Total requests
        total_requests = current_requests.count()
        previous_total = previous_requests.count()
        total_change = calculate_percentage_change(total_requests, previous_total)
        
        # Average processing time calculation (only for completed requests)
        completed_requests = current_requests.filter(status='Completed')
        previous_completed = previous_requests.filter(status='Completed')
        
        if completed_requests.exists():
            processing_times = []
            for req in completed_requests:
                days_diff = (req.last_updated.date() - req.requested_date.date()).days
                processing_times.append(days_diff)
            avg_processing_time = sum(processing_times) // len(processing_times)
        else:
            avg_processing_time = 0
            
        if previous_completed.exists():
            prev_processing_times = []
            for req in previous_completed:
                days_diff = (req.last_updated.date() - req.requested_date.date()).days
                prev_processing_times.append(days_diff)
            prev_avg_processing = sum(prev_processing_times) // len(prev_processing_times)
        else:
            prev_avg_processing = 0
            
        processing_change = calculate_change_days(avg_processing_time, prev_avg_processing)
        
        # Completion rate
        completion_rate = (completed_requests.count() / total_requests * 100) if total_requests > 0 else 0
        prev_completion_rate = (previous_completed.count() / previous_total * 100) if previous_total > 0 else 0
        completion_change = calculate_percentage_change(completion_rate, prev_completion_rate)
        
        # Urgent requests
        urgent_requests = current_requests.filter(priority__in=['Urgent', 'Critical']).count()
        prev_urgent = previous_requests.filter(priority__in=['Urgent', 'Critical']).count()
        urgent_change = calculate_percentage_change(urgent_requests, prev_urgent)
        
        # Overdue requests (requests older than 30 days and not completed)
        overdue_cutoff = timezone.now() - timedelta(days=30)
        overdue_requests = current_requests.filter(
            requested_date__lt=overdue_cutoff
        ).exclude(status='Completed').count()
        
        prev_overdue_cutoff = previous_end - timedelta(days=30)
        prev_overdue = previous_requests.filter(
            requested_date__lt=prev_overdue_cutoff
        ).exclude(status='Completed').count()
        overdue_change = calculate_percentage_change(overdue_requests, prev_overdue)
        
        # ===== STATUS DISTRIBUTION =====
        status_distribution = current_requests.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # ===== MONTHLY TRENDS =====
        monthly_data = []
        current_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)  # First day of current month

        for i in range(6):  # Last 6 months
            # Calculate the month we're looking at
            month_start = current_date - relativedelta(months=i)
            # Get the last day of that month
            month_end = month_start + relativedelta(months=1) - timedelta(days=1)
            # Ensure month_end time is end of day
            month_end = month_end.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            month_requests = RECRUITMENT.objects.filter(
                requested_date__gte=month_start,
                requested_date__lte=month_end
            ).count()
            
            monthly_data.append({
                'month': month_start.strftime('%b %Y'),
                'count': month_requests
            })

        monthly_data.reverse()  # Show chronologically
        
        # ===== PRIORITY DISTRIBUTION =====
        priority_distribution = current_requests.values('priority').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # ===== TOP PERFORMING MANAGERS =====
        manager_performance = []
        managers_with_requests = current_requests.values('managerid').distinct()

        for manager_data in managers_with_requests:
            manager_id = manager_data['managerid']
            try:
                manager = MANAGER.objects.get(id=manager_id)
                manager_requests = current_requests.filter(managerid=manager)
                
                # Calculate metrics for this manager
                total_mgr_requests = manager_requests.count()
                completed_mgr = manager_requests.filter(status='Completed').count()
                success_rate = (completed_mgr / total_mgr_requests * 100) if total_mgr_requests > 0 else 0
                
                # Average processing time for this manager
                mgr_completed = manager_requests.filter(status='Completed')
                if mgr_completed.exists():
                    mgr_processing_times = [
                        (req.last_updated.date() - req.requested_date.date()).days 
                        for req in mgr_completed
                    ]
                    mgr_avg_processing = sum(mgr_processing_times) // len(mgr_processing_times)
                else:
                    mgr_avg_processing = 0
                
                # Check if this manager is already in the list (avoid duplicates)
                existing_manager = next((item for item in manager_performance if item['manager'].id == manager.id), None)
                
                if not existing_manager:
                    manager_performance.append({
                        'manager': manager,
                        'requests': total_mgr_requests,
                        'avg_processing': mgr_avg_processing,
                        'success_rate': int(success_rate)
                    })
            except MANAGER.DoesNotExist:
                continue

        # Sort by success rate
        manager_performance.sort(key=lambda x: x['success_rate'], reverse=True)
        
        # ===== MOST REQUESTED POSITIONS =====
        position_requests = current_requests.values('position').annotate(
            request_count=Count('id'),
            total_personnel=Sum('total_personnel'),
            avg_timeline=Avg(
                Case(
                    When(status='Completed', 
                         then=F('last_updated') - F('requested_date')),
                    default=None
                )
            )
        ).order_by('-request_count')[:10]
        
        # ===== PERFORMANCE METRICS COMPARISON =====
        performance_metrics = [
            {
                'metric': 'Total Requests Received',
                'current': total_requests,
                'previous': previous_total,
                'change_percent': total_change['percent'],
                'change_direction': total_change['direction'],
                'target': 25,
                'status': get_status_vs_target(total_requests, 25)
            },
            {
                'metric': 'Average Processing Time',
                'current': f"{avg_processing_time} days",
                'previous': f"{prev_avg_processing} days",
                'change_percent': abs(processing_change['days']),
                'change_direction': processing_change['direction'],
                'target': "14 days",
                'status': get_processing_time_status(avg_processing_time, 14)
            },
            {
                'metric': 'Completion Rate',
                'current': f"{int(completion_rate)}%",
                'previous': f"{int(prev_completion_rate)}%",
                'change_percent': completion_change['percent'],
                'change_direction': completion_change['direction'],
                'target': "80%",
                'status': get_status_vs_target(completion_rate, 80)
            }
        ]
        
        # ===== INSIGHTS GENERATION =====
        insights = generate_insights(
            current_requests, avg_processing_time, prev_avg_processing,
            position_requests, manager_performance
        )
        
        context = {
            'hr': hr,
            'total_requests': total_requests,
            'total_change': total_change,
            'avg_processing_time': avg_processing_time,
            'processing_change': processing_change,
            'completion_rate': int(completion_rate),
            'completion_change': completion_change,
            'urgent_requests': urgent_requests,
            'urgent_change': urgent_change,
            'overdue_requests': overdue_requests,
            'overdue_change': overdue_change,
            'status_distribution': status_distribution,
            'monthly_data': json.dumps(monthly_data),
            'priority_distribution': priority_distribution,
            'manager_performance': manager_performance[:5],  # Top 5
            'position_requests': position_requests[:5],  # Top 5
            'performance_metrics': performance_metrics,
            'insights': insights,
            'days_period': days,
            'start_date': start_date,
            'end_date': end_date,
        }
        
        return render(request, 'hr/recruitment_analytics.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')

def calculate_percentage_change(current, previous):
    """Calculate percentage change and direction"""
    if previous == 0:
        if current > 0:
            return {'percent': 100, 'direction': 'positive'}
        else:
            return {'percent': 0, 'direction': 'neutral'}
    
    change = ((current - previous) / previous) * 100
    
    return {
        'percent': abs(int(change)),
        'direction': 'positive' if change >= 0 else 'negative'
    }

def calculate_change_days(current, previous):
    """Calculate change in days with direction"""
    change = current - previous
    
    return {
        'days': abs(change),
        'direction': 'negative' if change > 0 else 'positive' if change < 0 else 'neutral'
    }

def get_status_vs_target(current, target):
    """Determine status compared to target"""
    if current >= target:
        return "🎯 On Target"
    elif current >= target * 0.9:
        return "📈 Near Target"
    else:
        return "🔄 Below Target"

def get_processing_time_status(current, target):
    """Determine processing time status"""
    if current <= target:
        return "✅ On Target"
    elif current <= target * 1.2:
        return "⚠️ Slightly Above"
    else:
        return "🔴 Above Target"

def generate_insights(requests, avg_processing, prev_avg_processing, position_requests, manager_performance):
    """Generate intelligent insights based on data"""
    insights = []
    
    # Processing time insight
    if avg_processing > prev_avg_processing:
        insights.append({
            'title': 'Processing Time Trending Up',
            'description': f'Average processing time has increased by {avg_processing - prev_avg_processing} days compared to last period. Consider reviewing approval workflows for bottlenecks.'
        })
    elif avg_processing < prev_avg_processing:
        insights.append({
            'title': 'Processing Time Improving',
            'description': f'Average processing time has improved by {prev_avg_processing - avg_processing} days. Keep up the good work!'
        })
    
    # High demand positions insight
    if position_requests:
        top_position = position_requests[0]
        total_positions = sum([pos['request_count'] for pos in position_requests[:3]])
        percentage = (top_position['request_count'] / requests.count() * 100) if requests.count() > 0 else 0
        
        if percentage > 30:
            insights.append({
                'title': 'High Demand Positions',
                'description': f"{top_position['position']} accounts for {int(percentage)}% of all requests. Consider bulk recruitment strategies."
            })
    
    # Manager performance insight
    if manager_performance:
        best_manager = manager_performance[0]
        insights.append({
            'title': 'Manager Performance',
            'description': f"Requests from {best_manager['manager'].staffid.name} show {best_manager['success_rate']}% success rate. Share best practices with other managers."
        })
    
    return insights

def export_recruitment_report(request):
    """Export recruitment analytics report as PDF or Excel"""
    if not request.session.get('user_type') == 'hr':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    format_type = request.GET.get('format', 'pdf')
    days = int(request.GET.get('days', 30))
    
    try:
        hr_id = request.session.get('user_id')
        hr = HR.objects.get(id=hr_id)
        
        # Get data (reuse logic from analytics view)
        start_datetime = timezone.now() - timedelta(days=days)
        end_datetime = timezone.now()
        
        current_requests = RECRUITMENT.objects.filter(
            requested_date__gte=start_datetime,
            requested_date__lte=end_datetime
        ).select_related('managerid__staffid')
        
        if format_type == 'pdf':
            return generate_pdf_report(current_requests, hr, days)
        elif format_type == 'excel':
            return generate_excel_report(current_requests, hr, days)
        else:
            return JsonResponse({'error': 'Invalid format'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def generate_pdf_report(requests, hr, days):
    """Generate enhanced PDF report with charts using ReportLab"""
    # Get Malaysia time
    malaysia_time = get_malaysia_time()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recruitment_analytics_report_{malaysia_time.strftime("%Y%m%d")}.pdf"'
    
    # Create PDF document with custom page template
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        marginBottom=5,
        alignment=1,  # Center alignment
        textColor=colors.Color(0, 0.328, 0.929)  # #0053ED
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=30,
        alignment=1,
        textColor=colors.grey
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=15,
        textColor=colors.Color(0, 0.328, 0.929)
    )
    
    # ===== HEADER SECTION =====
    story.append(Paragraph("RECRUITMENT ANALYTICS REPORT", title_style))
    
    # Report metadata with Malaysia time
    report_info = f"""
    <b>Generated by:</b> {hr.staffid.name} ({hr.staffid.position})<br/>
    <b>Generated on:</b> {malaysia_time.strftime('%B %d, %Y at %I:%M %p')}<br/>
    <b>Analysis Period:</b> Last {days} days<br/>
    <b>Data Range:</b> {(malaysia_time - timedelta(days=days)).strftime('%B %d, %Y')} - {malaysia_time.strftime('%B %d, %Y')}
    """
    story.append(Paragraph(report_info, subtitle_style))
    story.append(Spacer(1, 20))
    
    # ===== EXECUTIVE SUMMARY =====
    story.append(Paragraph("EXECUTIVE SUMMARY", heading_style))
    
    # Calculate key metrics
    total_requests = requests.count()
    completed = requests.filter(status='Completed').count()
    pending = requests.filter(status='Pending').count()
    in_progress = requests.filter(status__in=['Under Review', 'In Progress']).count()
    urgent = requests.filter(priority__in=['Urgent', 'Critical']).count()
    completion_rate = (completed/total_requests*100) if total_requests > 0 else 0
    
    # KPI Cards in table format
    kpi_data = [
        ['Key Performance Indicators\n', '', '', ''],
        ['Total Requests', str(total_requests), 'Completion Rate', f"{completion_rate:.1f}%"],
        ['Completed', str(completed), 'Urgent Requests', str(urgent)],
        ['Pending', str(pending), 'In Progress', str(in_progress)]
    ]
    
    kpi_table = Table(kpi_data, colWidths=[2*inch, 1*inch, 2*inch, 1*inch])
    kpi_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0, 0.328, 0.929)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('SPAN', (0, 0), (-1, 0)),
        
        # Data rows
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),  # Left column labels
        ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),  # Right column labels
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Values center aligned
        ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Values center aligned
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.Color(0.95, 0.95, 0.95)),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(kpi_table)
    story.append(Spacer(1, 20))
    
    # ===== STATUS DISTRIBUTION CHART =====
    story.append(Paragraph("REQUEST STATUS DISTRIBUTION", heading_style))
    
    # Calculate status distribution
    status_counts = {}
    for status in ['Pending', 'Under Review', 'Approved', 'In Progress', 'Completed', 'Rejected']:
        count = requests.filter(status=status).count()
        if count > 0:
            status_counts[status] = count
    
    # Create status chart as table
    if status_counts:
        chart_data = [['Status', 'Count', 'Percentage']]
        for status, count in status_counts.items():
            percentage = (count / total_requests * 100)
            
            chart_data.append([
                status,
                str(count),
                f"{percentage:.1f}%"
            ])
        
        status_table = Table(chart_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        status_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0, 0.328, 0.929)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(status_table)
    story.append(Spacer(1, 20))
    
    # ===== PRIORITY DISTRIBUTION =====
    story.append(Paragraph("PRIORITY LEVEL ANALYSIS", heading_style))
    
    priority_counts = {}
    for priority in ['Low', 'Standard', 'High', 'Urgent', 'Critical']:
        count = requests.filter(priority=priority).count()
        if count > 0:
            priority_counts[priority] = count
    
    if priority_counts:
        priority_data = [['Priority Level', 'Count', 'Percentage', 'Risk Level']]
        for priority, count in priority_counts.items():
            percentage = (count / total_requests * 100)
            # Assign risk level without emojis
            if priority in ['Critical', 'Urgent']:
                risk = 'HIGH RISK'
            elif priority == 'High':
                risk = 'MEDIUM RISK'
            else:
                risk = 'LOW RISK'
                
            priority_data.append([
                priority,
                str(count),
                f"{percentage:.1f}%",
                risk
            ])
        
        priority_table = Table(priority_data, colWidths=[1.5*inch, 1*inch, 1.2*inch, 1.3*inch])
        priority_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0, 0.328, 0.929)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(priority_table)
    story.append(Spacer(1, 20))
    
    # ===== TOP POSITIONS ANALYSIS =====
    story.append(Paragraph("MOST REQUESTED POSITIONS", heading_style))
    
    # Get top positions
    from django.db.models import Count, Sum
    position_analysis = requests.values('position').annotate(
        request_count=Count('id'),
        total_personnel=Sum('total_personnel')
    ).order_by('-request_count')[:8]
    
    if position_analysis:
        position_data = [['Position', 'Requests', 'Personnel\nNeeded', 'Avg per\nRequest']]
        for pos in position_analysis:
            avg_personnel = pos['total_personnel'] / pos['request_count'] if pos['request_count'] > 0 else 0
            
            # Format position name with line breaks for long names
            position_name = pos['position']
            if len(position_name) > 15:
                # Split long position names into multiple lines
                words = position_name.split()
                formatted_position = ""
                current_line = ""
                for word in words:
                    if len(current_line + " " + word) <= 15:
                        current_line += (" " + word if current_line else word)
                    else:
                        formatted_position += (current_line + "\n")
                        current_line = word
                formatted_position += current_line
            else:
                formatted_position = position_name
            
            position_data.append([
                formatted_position,
                str(pos['request_count']),
                str(pos['total_personnel']),
                f"{avg_personnel:.1f}"
            ])
        
        position_table = Table(position_data, colWidths=[1.3*inch, 1*inch, 1.3*inch, 1.2*inch])
        position_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0, 0.328, 0.929)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        story.append(position_table)
    story.append(Spacer(1, 20))
    
    # ===== PAGE BREAK =====
    story.append(PageBreak())
    
    # ===== DETAILED REQUESTS TABLE =====
    story.append(Paragraph("DETAILED REQUEST LOG", heading_style))

    request_data = [['ID', 'Position', 'Manager', 'Status', 'Priority', 'Personnel', 'Date']]

    for req in requests.order_by('-requested_date')[:25]:  # Latest 25 requests
        # Format position name with line breaks for long names
        position_name = req.position
        if len(position_name) > 15:
            words = position_name.split()
            formatted_position = ""
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= 15:
                    current_line += (" " + word if current_line else word)
                else:
                    formatted_position += (current_line + "\n")
                    current_line = word
            formatted_position += current_line
        else:
            formatted_position = position_name
        
        # Convert to Malaysia time for display
        req_malaysia_time = req.requested_date.astimezone(pytz.timezone('Asia/Kuala_Lumpur'))
        
        request_data.append([
            str(req.id),
            formatted_position,
            req.managerid.staffid.name[:15] + '...' if len(req.managerid.staffid.name) > 15 else req.managerid.staffid.name,
            req.status,
            req.priority,
            str(req.total_personnel),
            req_malaysia_time.strftime('%m/%d/%Y')
        ])

    # Fixed column widths - reduced Position width and increased Personnel width
    request_table = Table(request_data, colWidths=[0.5*inch, 1.4*inch, 1.5*inch, 1.2*inch, 1*inch, 1*inch, 0.8*inch])
    request_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0, 0.328, 0.929)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # ID column center
        ('ALIGN', (4, 1), (6, -1), 'CENTER'),  # Priority, Personnel, Date center
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    # Add alternating row colors
    for i in range(2, len(request_data)):
        if i % 2 == 0:
            request_table.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.Color(0.98, 0.98, 0.98))
            ]))

    story.append(request_table)
    story.append(Spacer(1, 20))
    
    # ===== INSIGHTS & RECOMMENDATIONS =====
    story.append(Paragraph("KEY INSIGHTS & RECOMMENDATIONS", heading_style))
    
    insights_text = []
    
    # Generate dynamic insights
    if completion_rate < 50:
        insights_text.append("• Low Completion Rate: Consider reviewing approval processes and resource allocation.")
    
    if urgent > total_requests * 0.3:
        insights_text.append("• High Urgent Requests: Significant number of urgent requests may indicate planning issues.")
    
    most_requested = position_analysis[0] if position_analysis else None
    if most_requested:
        insights_text.append(f"• Top Position Demand: '{most_requested['position']}' has highest demand with {most_requested['request_count']} requests.")
    
    if pending > total_requests * 0.4:
        insights_text.append("• Processing Bottleneck: High number of pending requests suggests process optimization needed.")
    
    # Add default insights if none generated
    if not insights_text:
        insights_text.append("• Stable Operations: Recruitment processes are operating within normal parameters.")
        insights_text.append("• Continue Monitoring: Regular review of metrics recommended for continued optimization.")
    
    insights_paragraph = Paragraph("<br/>".join(insights_text), styles['Normal'])
    story.append(insights_paragraph)
    story.append(Spacer(1, 20))
    
    # ===== FOOTER =====
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=10,
        alignment=1,
        textColor=colors.grey
    )
    
    footer_text = f"""
    <br/><br/>
    ________________________________________________________________________<br/>
    KOOP-KPMIM Human Resources Management System<br/>
    Generated by HRMS Analytics Engine | Confidential Document<br/>
    Report ID: RPT-{malaysia_time.strftime('%Y%m%d%H%M%S')}
    """
    story.append(Paragraph(footer_text, footer_style))
    
    # Build PDF
    doc.build(story)
    return response

def generate_excel_report(requests, hr, days):
    """Generate Excel report using xlsxwriter"""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # Define formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#0053ED',
        'font_color': 'white',
        'align': 'center'
    })
    
    data_format = workbook.add_format({
        'align': 'center'
    })
    
    # Summary sheet
    summary_sheet = workbook.add_worksheet('Summary')
    
    # Write summary data
    summary_sheet.write('A1', 'Recruitment Analytics Report', workbook.add_format({'bold': True, 'font_size': 16}))
    summary_sheet.write('A3', f'Generated by: {hr.staffid.name}')
    summary_sheet.write('A4', f'Date: {timezone.now().strftime("%B %d, %Y")}')
    summary_sheet.write('A5', f'Period: Last {days} days')
    
    # Summary statistics
    summary_sheet.write('A7', 'Metric', header_format)
    summary_sheet.write('B7', 'Value', header_format)
    
    completed = requests.filter(status='Completed').count()
    
    summary_data = [
        ['Total Requests', requests.count()],
        ['Completed', completed],
        ['Pending', requests.filter(status='Pending').count()],
        ['In Progress', requests.filter(status__in=['Under Review', 'In Progress']).count()],
        ['Completion Rate', f"{(completed/requests.count()*100):.1f}%" if requests.count() > 0 else "0%"]
    ]
    
    for row, (metric, value) in enumerate(summary_data, start=8):
        summary_sheet.write(row, 0, metric, data_format)
        summary_sheet.write(row, 1, value, data_format)
    
    # Detailed data sheet
    detail_sheet = workbook.add_worksheet('Detailed Requests')
    
    # Headers
    headers = ['Request ID', 'Position', 'Manager', 'Status', 'Priority', 'Personnel', 'Date Requested', 'Last Updated']
    for col, header in enumerate(headers):
        detail_sheet.write(0, col, header, header_format)
    
    # Data rows
    for row, req in enumerate(requests.order_by('-requested_date'), start=1):
        detail_sheet.write(row, 0, req.id, data_format)
        detail_sheet.write(row, 1, req.position, data_format)
        detail_sheet.write(row, 2, req.managerid.staffid.name, data_format)
        detail_sheet.write(row, 3, req.status, data_format)
        detail_sheet.write(row, 4, req.priority, data_format)
        detail_sheet.write(row, 5, req.total_personnel, data_format)
        detail_sheet.write(row, 6, req.requested_date.strftime('%Y-%m-%d'), data_format)
        detail_sheet.write(row, 7, req.last_updated.strftime('%Y-%m-%d'), data_format)
    
    # Auto-adjust column widths
    for sheet in [summary_sheet, detail_sheet]:
        for col in range(8):
            sheet.set_column(col, col, 15)
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="recruitment_report_{timezone.now().strftime("%Y%m%d")}.xlsx"'
    
    return response

# In-memory storage for scheduled reports (in production, use database)
scheduled_reports = {}

def schedule_recruitment_report(request):
    """Schedule recurring reports"""
    if not request.session.get('user_type') == 'hr':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            hr_id = request.session.get('user_id')
            hr = HR.objects.get(id=hr_id)
            
            # Generate unique schedule ID
            schedule_id = str(uuid.uuid4())
            
            # Store schedule info
            schedule_info = {
                'id': schedule_id,
                'hr_id': hr_id,
                'email': data.get('email', hr.staffid.email),
                'frequency': data.get('frequency', 'weekly'),  # daily, weekly, monthly
                'format': data.get('format', 'pdf'),
                'days_period': data.get('days_period', 30),
                'created_at': timezone.now().isoformat(),
                'active': True
            }
            
            scheduled_reports[schedule_id] = schedule_info
            
            # Schedule the first report (in production, use Celery or similar)
            schedule_next_report(schedule_info)
            
            return JsonResponse({
                'success': True,
                'message': 'Report scheduled successfully',
                'schedule_id': schedule_id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET request - return current schedules
    hr_id = request.session.get('user_id')
    user_schedules = [
        schedule for schedule in scheduled_reports.values() 
        if schedule['hr_id'] == hr_id and schedule['active']
    ]
    
    return JsonResponse({
        'schedules': user_schedules
    })

def schedule_next_report(schedule_info):
    """Schedule the next report delivery"""
    frequency_map = {
        'daily': 1,
        'weekly': 7,
        'monthly': 30
    }
    
    days = frequency_map.get(schedule_info['frequency'], 7)
    next_run = timezone.now() + timedelta(days=days)
    
    # In production, use Celery or similar task queue
    # For demo purposes, we'll just log the scheduling
    print(f"Report {schedule_info['id']} scheduled for {next_run}")

def cancel_scheduled_report(request, schedule_id):
    """Cancel a scheduled report"""
    if not request.session.get('user_type') == 'hr':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if schedule_id in scheduled_reports:
        scheduled_reports[schedule_id]['active'] = False
        return JsonResponse({'success': True, 'message': 'Schedule cancelled'})
    
    return JsonResponse({'error': 'Schedule not found'}, status=404)

# Enhanced recruitment_attachments function
def recruitment_attachments(request, request_id):
    """
    Enhanced attachment management with file upload handling
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
        
        # Get the specific recruitment request
        recruitment_request = get_object_or_404(RECRUITMENT, id=request_id)
        
        # Handle POST requests for attachment management
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'upload_attachment':
                # Handle file upload
                file = request.FILES.get('attachment_file')
                attachment_type = request.POST.get('attachment_type')
                description = request.POST.get('description', '').strip()
                
                if file and attachment_type:
                    try:
                        # Basic file validation
                        max_size = 10 * 1024 * 1024  # 10MB
                        if file.size > max_size:
                            messages.error(request, 'File size must be less than 10MB.')
                            return redirect('hr_recruitment_attachments', request_id=request_id)
                        
                        # Check file extension
                        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg']
                        file_extension = file.name.split('.')[-1].lower()
                        if f'.{file_extension}' not in allowed_extensions:
                            messages.error(request, 'File type not allowed.')
                            return redirect('hr_recruitment_attachments', request_id=request_id)
                        
                        # Create attachment record
                        attachment = RECRUITMENT_ATTACHMENTS.objects.create(
                            recruitment=recruitment_request,
                            file_name=file.name,
                            file_path=file,  # Django will handle the file saving
                            uploaded_by=hr,
                            attachment_type=attachment_type,
                            description=description
                        )
                        
                        messages.success(request, f'Attachment "{file.name}" uploaded successfully!')
                        return redirect('hr_recruitment_attachments', request_id=request_id)
                        
                    except Exception as e:
                        messages.error(request, f'Error uploading file: {str(e)}')
                else:
                    messages.error(request, 'File and attachment type are required.')
            
            elif action == 'delete_attachment':
                attachment_id = request.POST.get('attachment_id')
                if attachment_id:
                    try:
                        # Get and delete attachment
                        attachment = get_object_or_404(RECRUITMENT_ATTACHMENTS, id=attachment_id, recruitment=recruitment_request)
                        
                        # Delete the physical file if it exists
                        if attachment.file_path:
                            try:
                                attachment.file_path.delete(save=False)
                            except:
                                pass  # File might not exist physically
                        
                        attachment_name = attachment.file_name
                        attachment.delete()
                        
                        messages.success(request, f'Attachment "{attachment_name}" deleted successfully!')
                        return redirect('hr_recruitment_attachments', request_id=request_id)
                        
                    except Exception as e:
                        messages.error(request, f'Error deleting attachment: {str(e)}')
        
        # GET request - display attachments page
        # Get actual attachments from database
        attachments = RECRUITMENT_ATTACHMENTS.objects.filter(recruitment=recruitment_request).order_by('-uploaded_date')
        
        # Calculate statistics
        total_attachments = attachments.count()
        total_size_bytes = 0
        job_desc_count = 0
        budget_count = 0
        supporting_count = 0
        
        for attachment in attachments:
            # Count by type
            if attachment.attachment_type == 'Job Description':
                job_desc_count += 1
            elif attachment.attachment_type == 'Budget Approval':
                budget_count += 1
            elif attachment.attachment_type == 'Supporting Document':
                supporting_count += 1
            
            # Calculate total file size
            try:
                if attachment.file_path and hasattr(attachment.file_path, 'size'):
                    total_size_bytes += attachment.file_path.size
            except:
                pass  # Skip if file doesn't exist or size unavailable
        
        # Format total size
        def format_file_size(size_bytes):
            if size_bytes == 0:
                return "0 MB"
            elif size_bytes < 1024:
                return f"{size_bytes} Bytes"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
        
        total_size = format_file_size(total_size_bytes)
        
        context = {
            'hr': hr,
            'recruitment_request': recruitment_request,
            'attachments': attachments,
            'total_size': total_size,
            'job_desc_count': job_desc_count,
            'budget_count': budget_count,
            'supporting_count': supporting_count,
        }
        
        return render(request, 'hr/recruitment_attachments.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')
    
def download_attachment(request, attachment_id):
    """
    Download a recruitment attachment file
    """
    # Check if user is authorized HR
    if not request.session.get('user_type') == 'hr':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get the attachment
        attachment = get_object_or_404(RECRUITMENT_ATTACHMENTS, id=attachment_id)
        
        # Check if file exists
        if not attachment.file_path or not attachment.file_path.name:
            messages.error(request, "File not found.")
            return redirect('hr_recruitment_attachments', request_id=attachment.recruitment.id)
        
        try:
            # Open the file
            file_path = attachment.file_path.path
            
            # Check if file physically exists
            if not os.path.exists(file_path):
                messages.error(request, "File no longer exists on server.")
                return redirect('hr_recruitment_attachments', request_id=attachment.recruitment.id)
            
            # Determine content type based on file extension
            file_extension = attachment.file_name.split('.')[-1].lower()
            content_type_map = {
                'pdf': 'application/pdf',
                'doc': 'application/msword',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'xls': 'application/vnd.ms-excel',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
            }
            
            content_type = content_type_map.get(file_extension, 'application/octet-stream')
            
            # Create response with file
            with open(file_path, 'rb') as file:
                response = HttpResponse(file.read(), content_type=content_type)
                response['Content-Disposition'] = f'attachment; filename="{attachment.file_name}"'
                return response
                
        except Exception as e:
            messages.error(request, f"Error accessing file: {str(e)}")
            return redirect('hr_recruitment_attachments', request_id=attachment.recruitment.id)
        
    except RECRUITMENT_ATTACHMENTS.DoesNotExist:
        messages.error(request, "Attachment not found.")
        return redirect('hr_recruitment')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')

# Add this view function to your HRMS/views.py

def recruitment_status_history(request, request_id):
    """
    View status change history for a specific recruitment request
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
        
        # Get the specific recruitment request
        recruitment_request = get_object_or_404(RECRUITMENT, id=request_id)
        
        # Get status history if RECRUITMENT_STATUS_HISTORY model exists
        # Otherwise, create mock data for display
        try:
            # Try to get real status history
            from .models import RECRUITMENT_STATUS_HISTORY
            status_history = RECRUITMENT_STATUS_HISTORY.objects.filter(
                recruitment=recruitment_request
            ).order_by('-changed_date')
        except (ImportError, AttributeError):
            # If model doesn't exist, use empty queryset
            status_history = []
        
        context = {
            'hr': hr,
            'recruitment_request': recruitment_request,
            'status_history': status_history,
        }
        
        return render(request, 'hr/recruitment_status_history.html', context)
        
    except HR.DoesNotExist:
        messages.error(request, "HR user not found. Please login again")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('hr_recruitment')    

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
    
def manager_profile(request):
    # Check if user is authenticated and is a manager
    if not request.session.get('user_type') == 'manager':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    user_id = request.session.get('user_id')
    manager = MANAGER.objects.get(id=user_id)
    # Handle form submission
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Update password if provided
        if current_password and new_password and confirm_password:
            if check_password(current_password, manager.password):
                if new_password == confirm_password:
                    manager.password = make_password(new_password)
                    manager.save()
                    messages.success(request, 'Password updated successfully!')
                else:
                    messages.error(request, 'New password and confirm password do not match!')
            else:
                messages.error(request, 'Current password is incorrect!')
                
    context = {
        'manager': manager
    }
    return render(request, 'manager/profile.html', context)

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
    Enhanced view for managers to submit comprehensive recruitment requests
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
            # Get basic required fields
            position = request.POST.get('position', '').strip()
            total_personnel_str = request.POST.get('total_personnel', '').strip()
            reason = request.POST.get('reason', '').strip()
            priority = request.POST.get('priority', '').strip()
            justification_type = request.POST.get('justification_type', '').strip()
            
            # Get optional fields
            expected_timeline = request.POST.get('expected_timeline', '2-4 weeks')
            target_start_date = request.POST.get('target_start_date', '').strip()
            employment_type = request.POST.get('employment_type', 'Full-time')
            remote_work_option = request.POST.get('remote_work_option', 'On-site')
            salary_range_min = request.POST.get('salary_range_min', '').strip()
            salary_range_max = request.POST.get('salary_range_max', '').strip()
            required_qualifications = request.POST.get('required_qualifications', '').strip()
            job_description = request.POST.get('job_description', '').strip()
            
            # Validate required fields
            if not position or not total_personnel_str or not reason or not priority or not justification_type:
                messages.error(request, 'All required fields must be filled.')
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
            
            # Validate field lengths
            if len(position) > 100:
                messages.error(request, 'Position title is too long (maximum 100 characters).')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
            
            if len(reason) > 1000:
                messages.error(request, 'Justification is too long (maximum 1000 characters).')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
            
            
            

            # Validate priority and justification type
            valid_priorities = ['Low', 'Standard', 'High', 'Urgent', 'Critical']
            valid_justification_types = ['New Position', 'Replacement', 'Expansion', 'Temporary Cover', 'Project Based']
            
            if priority not in valid_priorities:
                messages.error(request, 'Invalid priority level selected.')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
            
            if justification_type not in valid_justification_types:
                messages.error(request, 'Invalid request type selected.')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
            
            # Validate salary range if provided
            salary_min_decimal = None
            salary_max_decimal = None
            
            if salary_range_min:
                try:
                    salary_min_decimal = Decimal(salary_range_min)
                    if salary_min_decimal < 0:
                        messages.error(request, 'Minimum salary cannot be negative.')
                        return render(request, 'manager/recruitment_request.html', {
                            'manager': manager
                        })
                except (ValueError, InvalidOperation):
                    messages.error(request, 'Please enter a valid minimum salary amount.')
                    return render(request, 'manager/recruitment_request.html', {
                        'manager': manager
                    })
            
            if salary_range_max:
                try:
                    salary_max_decimal = Decimal(salary_range_max)
                    if salary_max_decimal < 0:
                        messages.error(request, 'Maximum salary cannot be negative.')
                        return render(request, 'manager/recruitment_request.html', {
                            'manager': manager
                        })
                except (ValueError, InvalidOperation):
                    messages.error(request, 'Please enter a valid maximum salary amount.')
                    return render(request, 'manager/recruitment_request.html', {
                        'manager': manager
                    })
            
            # Validate salary range logic
            if salary_min_decimal and salary_max_decimal and salary_min_decimal > salary_max_decimal:
                messages.error(request, 'Minimum salary cannot be higher than maximum salary.')
                return render(request, 'manager/recruitment_request.html', {
                    'manager': manager
                })
            
            # Validate target start date if provided
            target_start_date_parsed = None
            if target_start_date:
                try:
                    target_start_date_parsed = parse_date(target_start_date)
                    if target_start_date_parsed and target_start_date_parsed < timezone.now().date():
                        messages.error(request, 'Preferred start date cannot be in the past.')
                        return render(request, 'manager/recruitment_request.html', {
                            'manager': manager
                        })
                except ValueError:
                    messages.error(request, 'Invalid date format for preferred start date.')
                    return render(request, 'manager/recruitment_request.html', {
                        'manager': manager
                    })
            
            # Calculate expected completion date based on timeline
            expected_completion_date = None
            if target_start_date_parsed:
                timeline_days = {
                    '1-2 weeks': 14,
                    '2-4 weeks': 28,
                    '1-2 months': 60,
                    '2-3 months': 90,
                    '3+ months': 120
                }
                days_to_add = timeline_days.get(expected_timeline, 28)
                expected_completion_date = target_start_date_parsed - timedelta(days=7)  # Hiring should complete 1 week before start
            
            # Get team information for department field
            try:
                team = TEAM.objects.get(managerid=manager)
                department = team.name if team.name else f"{manager.staffid.position} Department"
            except TEAM.DoesNotExist:
                department = f"{manager.staffid.position} Department"
            
            try:
                # Create the recruitment request with comprehensive data
                recruitment_request = RECRUITMENT.objects.create(
                    # Basic Information
                    position=position,
                    reason=reason,
                    total_personnel=total_personnel,
                    managerid=manager,
                    
                    # Status and Priority
                    status='Pending',
                    priority=priority,
                    
                    # Timeline Information
                    target_start_date=target_start_date_parsed,
                    expected_completion_date=expected_completion_date,
                    expected_timeline=expected_timeline,
                    
                    # Job Details
                    job_description=job_description,
                    required_qualifications=required_qualifications,
                    salary_range_min=salary_min_decimal,
                    salary_range_max=salary_max_decimal,
                    employment_type=employment_type,
                    
                    # Department and Location
                    department=department,
                    work_location='KOOP-KPMIM Premises',
                    remote_work_option=remote_work_option,
                    
                    # Business Justification
                    business_justification=reason,  # Use the same as reason for now
                    justification_type=justification_type,
                    
                    # Additional Settings
                    is_confidential=False,
                    external_posting_allowed=True,
                )
                
                # Create success message with details
                personnel_text = "person" if total_personnel == 1 else "people"
                priority_text = f" with {priority.lower()} priority" if priority != 'Standard' else ""
                timeline_text = f" Expected timeline: {expected_timeline}."
                
                success_message = (
                    f'Recruitment request submitted successfully! '
                    f'Request #{recruitment_request.id} for {total_personnel} {personnel_text} '
                    f'for {position} position{priority_text} has been sent to HR for review.{timeline_text}'
                )
                
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
            'manager': manager,
            'today': timezone.now().date(),
        }
        
        return render(request, 'manager/recruitment_request.html', context)
    
    except MANAGER.DoesNotExist:
        messages.error(request, "Manager profile not found. Please login again.")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('managermenu')

# staff

def staff_policies(request):
    """View for staff to view company policies and procedures"""
    # Check if user is authenticated and is staff
    if not request.session.get('user_type') == 'staff':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get staff information
        staff_id = request.session.get('user_id')
        staff = STAFF.objects.get(id=staff_id)
        
        # Get all policies ordered by most recent first
        policies = POLICIES.objects.all().order_by('-enacted')
        
        # Count total policies
        policies_count = policies.count()
        
        context = {
            'staff': staff,
            'policies': policies,
            'policies_count': policies_count,
        }
        
        return render(request, 'staff/policies.html', context)
        
    except STAFF.DoesNotExist:
        messages.error(request, "Staff profile not found. Please login again.")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('staffmenu')

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
    
def staff_personal_info(request):
    """View for staff to view and update their personal information"""
    # Check if user is authenticated and is staff
    if not request.session.get('user_type') == 'staff':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get staff information
        staff_id = request.session.get('user_id')
        staff = STAFF.objects.get(id=staff_id)
        
        # Get or create address information
        try:
            address = ADDRESS.objects.get(staffid=staff)
        except ADDRESS.DoesNotExist:
            address = None
        
        if request.method == 'POST':
            section = request.POST.get('section')
            
            if section == 'basic_info':
                # Update basic information
                name = request.POST.get('name', '').strip()
                email = request.POST.get('email', '').strip()
                phone = request.POST.get('phone', '').strip()
                gender = request.POST.get('gender', '')
                status = request.POST.get('status', '')
                bank_number = request.POST.get('bank_number', '').strip()
                emergency_contact = request.POST.get('emergency_contact', '').strip()
                
                # Validate required fields
                if not name:
                    messages.error(request, 'Name is required.')
                    return render(request, 'staff/personal_info.html', {
                        'staff': staff,
                        'address': address
                    })
                
                # Validate email format if provided
                if email:
                    import re
                    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    if not re.match(email_pattern, email):
                        messages.error(request, 'Please enter a valid email address.')
                        return render(request, 'staff/personal_info.html', {
                            'staff': staff,
                            'address': address
                        })
                
                # Validate phone number if provided
                if phone:
                    # Remove spaces and special characters for validation
                    phone_clean = re.sub(r'[^\d+]', '', phone)
                    if len(phone_clean) < 10 or len(phone_clean) > 15:
                        messages.error(request, 'Please enter a valid phone number (10-15 digits).')
                        return render(request, 'staff/personal_info.html', {
                            'staff': staff,
                            'address': address
                        })
                
                try:
                    # Update staff information
                    staff.name = name
                    staff.email = email
                    staff.phone = phone
                    staff.gender = gender
                    staff.status = status
                    staff.bank_number = bank_number
                    staff.emergency_contact = emergency_contact
                    staff.save()
                    
                    messages.success(request, 'Your personal information has been updated successfully!')
                    
                except Exception as e:
                    messages.error(request, f'Error updating personal information: {str(e)}')
            
            elif section == 'address':
                # Update address information
                address1 = request.POST.get('address1', '').strip()
                address2 = request.POST.get('address2', '').strip()
                poscode_str = request.POST.get('poscode', '').strip()
                state = request.POST.get('state', '').strip()
                
                # Validate postal code if provided
                poscode = None
                if poscode_str:
                    try:
                        poscode = int(poscode_str)
                        if poscode < 10000 or poscode > 99999:
                            messages.error(request, 'Please enter a valid 5-digit postal code.')
                            return render(request, 'staff/personal_info.html', {
                                'staff': staff,
                                'address': address
                            })
                    except ValueError:
                        messages.error(request, 'Please enter a valid postal code (numbers only).')
                        return render(request, 'staff/personal_info.html', {
                            'staff': staff,
                            'address': address
                        })
                
                try:
                    # Update or create address
                    if address:
                        # Update existing address
                        address.address1 = address1
                        address.address2 = address2
                        address.poscode = poscode if poscode else 0
                        address.state = state
                        address.save()
                    else:
                        # Create new address
                        address = ADDRESS.objects.create(
                            staffid=staff,
                            address1=address1,
                            address2=address2,
                            poscode=poscode if poscode else 0,
                            state=state
                        )
                    
                    messages.success(request, 'Your address information has been updated successfully!')
                    
                except Exception as e:
                    messages.error(request, f'Error updating address information: {str(e)}')
            
            elif section == 'password':
                # Change password
                current_password = request.POST.get('current_password')
                new_password = request.POST.get('new_password')
                confirm_password = request.POST.get('confirm_password')
                
                # Validate current password
                if not check_password(current_password, staff.password):
                    messages.error(request, 'Current password is incorrect.')
                    return render(request, 'staff/personal_info.html', {
                        'staff': staff,
                        'address': address
                    })
                
                # Validate new password
                if new_password != confirm_password:
                    messages.error(request, 'New password and confirm password do not match.')
                    return render(request, 'staff/personal_info.html', {
                        'staff': staff,
                        'address': address
                    })
                
                # Validate password strength
                if not validate_password_strength(new_password):
                    messages.error(request, 'Password must be at least 8 characters with a capital letter, number, and symbol.')
                    return render(request, 'staff/personal_info.html', {
                        'staff': staff,
                        'address': address
                    })
                
                # Check if new password is different from current
                if check_password(new_password, staff.password):
                    messages.error(request, 'New password must be different from current password.')
                    return render(request, 'staff/personal_info.html', {
                        'staff': staff,
                        'address': address
                    })
                
                try:
                    # Update password
                    staff.password = make_password(new_password)
                    staff.save()
                    
                    messages.success(request, 'Your password has been changed successfully!')
                    
                except Exception as e:
                    messages.error(request, f'Error changing password: {str(e)}')
            
            else:
                messages.error(request, 'Invalid form submission.')
            
            # Refresh address after potential creation
            try:
                address = ADDRESS.objects.get(staffid=staff)
            except ADDRESS.DoesNotExist:
                address = None
            
            return render(request, 'staff/personal_info.html', {
                'staff': staff,
                'address': address
            })
        
        # GET request - display the personal information page
        context = {
            'staff': staff,
            'address': address,
        }
        
        return render(request, 'staff/personal_info.html', context)
        
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('staffmenu')

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
        
        # Check if staff is part of any team (either as member or manager)
        # Check if staff is a team member
        is_team_member = TEAM_MEMBERSHIP.objects.filter(staff=staff).exists()
        
        # Check if staff is a manager (team leader)
        is_team_manager = False
        try:
            manager = MANAGER.objects.get(staffid=staff)
            is_team_manager = TEAM.objects.filter(managerid=manager).exists()
        except MANAGER.DoesNotExist:
            is_team_manager = False
        
        # Staff has team if they are either a team member or team manager
        has_team = is_team_member or is_team_manager
        
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
            # Only process POST if staff has a team
            if not has_team:
                messages.error(request, 'You cannot apply for leave without being assigned to a team.')
                return render(request, 'staff/leave_application.html', {
                    'staff': staff,
                    'has_team': has_team,
                    'leave_balance': leave_balance,
                    'today': timezone.now().date()
                })
            
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            reason = request.POST.get('reason', '').strip()
            
            # Validate input
            if not start_date_str or not end_date_str or not reason:
                messages.error(request, 'All fields are required.')
                return render(request, 'staff/leave_application.html', {
                    'staff': staff,
                    'has_team': has_team,
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
                        'has_team': has_team,
                        'leave_balance': leave_balance,
                        'today': timezone.now().date()
                    })
                
                # Validate date logic
                if start_date > end_date:
                    messages.error(request, 'Start date cannot be after end date.')
                    return render(request, 'staff/leave_application.html', {
                        'staff': staff,
                        'has_team': has_team,
                        'leave_balance': leave_balance,
                        'today': timezone.now().date()
                    })
                
                # Check if start date is not in the past
                if start_date < timezone.now().date():
                    messages.error(request, 'Leave application cannot be for past dates.')
                    return render(request, 'staff/leave_application.html', {
                        'staff': staff,
                        'has_team': has_team,
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
                        'has_team': has_team,
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
                        'has_team': has_team,
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
                    'has_team': has_team,
                    'leave_balance': leave_balance,
                    'today': timezone.now().date()
                })
            except Exception as e:
                messages.error(request, f'An error occurred while processing your application: {str(e)}')
                return render(request, 'staff/leave_application.html', {
                    'staff': staff,
                    'has_team': has_team,
                    'leave_balance': leave_balance,
                    'today': timezone.now().date()
                })
        
        # GET request - show the form
        context = {
            'staff': staff,
            'has_team': has_team,
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
        
        # Check if staff is part of any team (either as member or manager)
        # Check if staff is a team member
        is_team_member = TEAM_MEMBERSHIP.objects.filter(staff=staff).exists()
        
        # Check if staff is a manager (team leader)
        is_team_manager = False
        try:
            manager = MANAGER.objects.get(staffid=staff)
            is_team_manager = TEAM.objects.filter(managerid=manager).exists()
        except MANAGER.DoesNotExist:
            is_team_manager = False
        
        # Staff has team if they are either a team member or team manager
        has_team = is_team_member or is_team_manager
        
        # If staff doesn't have a team, redirect to leave application with error
        if not has_team:
            messages.error(request, 'You cannot view leave status without being assigned to a team.')
            return redirect('staff_leave_application')
        
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
            'has_team': has_team,
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
      
def staff_payslip(request):
    """View for staff to view and download their pay slip"""
    # Check if user is authenticated and is staff
    if not request.session.get('user_type') == 'staff':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get staff information
        staff_id = request.session.get('user_id')
        staff = STAFF.objects.get(id=staff_id)
        
        # Get payroll information for this staff
        try:
            payroll = PAYROLL.objects.get(staffid=staff)
            
            # Calculate total earnings and deductions
            total_earnings = payroll.base + payroll.allowance + payroll.bonus
            total_deductions = payroll.epf_employee + payroll.pcb
            
            # Calculate year-to-date figures (simple calculation for demo)
            # In a real system, you'd have multiple payroll records per year
            current_month = timezone.now().month
            ytd_earnings = total_earnings * current_month
            ytd_epf = payroll.epf_employee * current_month
            ytd_tax = payroll.pcb * current_month
            
            # Format current month and pay date
            current_month_str = timezone.now().strftime('%B %Y')
            pay_date = timezone.now().strftime('%B %d, %Y')
            
            context = {
                'staff': staff,
                'payroll': payroll,
                'total_earnings': total_earnings,
                'total_deductions': total_deductions,
                'current_month': current_month_str,
                'pay_date': pay_date,
                'ytd_earnings': ytd_earnings,
                'ytd_epf': ytd_epf,
                'ytd_tax': ytd_tax,
            }
            
        except PAYROLL.DoesNotExist:
            # No payroll record found for this staff
            context = {
                'staff': staff,
                'payroll': None,
            }
        
        return render(request, 'staff/payslip.html', context)
        
    except STAFF.DoesNotExist:
        messages.error(request, "Staff profile not found. Please login again.")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('staffmenu')
    
def staff_payslip_pdf(request):
    """Generate and download pay slip as PDF"""
    # Check if user is authenticated and is staff
    if not request.session.get('user_type') == 'staff':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    try:
        # Get Malaysia time
        malaysia_time = get_malaysia_time()
        
        # Get staff information
        staff_id = request.session.get('user_id')
        staff = STAFF.objects.get(id=staff_id)
        
        # Get payroll information
        try:
            payroll = PAYROLL.objects.get(staffid=staff)
        except PAYROLL.DoesNotExist:
            messages.error(request, "No payroll information found. Please contact HR.")
            return redirect('staff_payslip')
        
        # Create PDF response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="payslip_{staff.id}_{malaysia_time.strftime("%Y_%m")}.pdf"'
        
        # Create PDF document
        doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#0053ED')
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=20,
            alignment=1,
            textColor=colors.HexColor('#4A4A4A')
        )
        
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#0053ED'),
            borderWidth=1,
            borderColor=colors.HexColor('#0053ED'),
            borderPadding=5
        )
        
        # Company Header
        story.append(Paragraph("KOOP-KPMIM", title_style))
        story.append(Paragraph("Employee Pay Slip", subtitle_style))
        story.append(Paragraph(f"Pay Period: {malaysia_time.strftime('%B %Y')}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Employee Information Table
        employee_data = [
            ['Employee Information', 'Payment Details'],
            [f'Employee ID: {staff.id}', f'Pay Date: {malaysia_time.strftime("%B %d, %Y")}'],
            [f'Name: {staff.name}', f'Bank Account: {staff.bank_number or "Not provided"}'],
            [f'Position: {staff.position}', f'Status: {staff.status or "Not specified"}'],
            [f'Email: {staff.email or "Not provided"}', f'Phone: {staff.phone or "Not provided"}']
        ]
        
        employee_table = Table(employee_data, colWidths=[3*inch, 3*inch])
        employee_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0053ED')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))
        
        story.append(employee_table)
        story.append(Spacer(1, 30))
        
        # Calculate totals
        total_earnings = payroll.base + payroll.allowance + payroll.bonus
        total_deductions = payroll.epf_employee + payroll.pcb
        
        # Payroll Details Table
        payroll_data = [
            ['Description', 'Amount (RM)'],
            ['EARNINGS', ''],
            ['Base Salary', f'{payroll.base:.2f}'],
        ]
        
        # Add allowance if > 0
        if payroll.allowance > 0:
            payroll_data.append(['Allowance', f'{payroll.allowance:.2f}'])
        
        # Add bonus if > 0
        if payroll.bonus > 0:
            payroll_data.append(['Bonus', f'{payroll.bonus:.2f}'])
        
        # Add total earnings
        payroll_data.extend([
            ['Total Earnings', f'{total_earnings:.2f}'],
            ['', ''],
            ['DEDUCTIONS', ''],
            ['EPF Employee Contribution (11%)', f'{payroll.epf_employee:.2f}']
        ])
        
        # Add PCB if > 0
        if payroll.pcb > 0:
            payroll_data.append(['Income Tax (PCB)', f'{payroll.pcb:.2f}'])
        
        # Add total deductions and net salary
        payroll_data.extend([
            ['Total Deductions', f'{total_deductions:.2f}'],
            ['', ''],
            ['NET SALARY', f'{payroll.net_salary:.2f}']
        ])
        
        payroll_table = Table(payroll_data, colWidths=[4*inch, 2*inch])
        
        # Table styling
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0053ED')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]
        
        # Highlight section headers
        earnings_row = 1
        deductions_start = -1
        net_salary_row = -1
        
        for i, row in enumerate(payroll_data):
            if row[0] == 'EARNINGS':
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.lightgrey))
                table_style.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
            elif row[0] == 'DEDUCTIONS':
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.lightgrey))
                table_style.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
                deductions_start = i
            elif row[0] == 'Total Earnings':
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#E0E0E0')))
                table_style.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
            elif row[0] == 'Total Deductions':
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#E0E0E0')))
                table_style.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
            elif row[0] == 'NET SALARY':
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#0053ED')))
                table_style.append(('TEXTCOLOR', (0, i), (-1, i), colors.whitesmoke))
                table_style.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
                table_style.append(('FONTSIZE', (0, i), (-1, i), 14))
                # Add extra padding for NET SALARY row
                table_style.append(('TOPPADDING', (0, i), (-1, i), 15))
                table_style.append(('BOTTOMPADDING', (0, i), (-1, i), 15))
                net_salary_row = i
        
        payroll_table.setStyle(TableStyle(table_style))
        story.append(payroll_table)
        story.append(Spacer(1, 30))
        
       
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            alignment=1,
            textColor=colors.grey
        )
        
        story.append(Paragraph("This is a computer-generated pay slip and does not require a signature.", footer_style))
        story.append(Paragraph(f"Generated on: {malaysia_time.strftime('%B %d, %Y at %I:%M %p')}", footer_style))
        
        # Build PDF
        doc.build(story)
        return response
        
    except STAFF.DoesNotExist:
        messages.error(request, "Staff profile not found. Please login again.")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        return redirect('staff_payslip')

def staff_submit_feedback(request):
    """
    View for staff to submit feedback or complaints
    """
    # Check user authorization
    if not request.session.get('user_type') == 'staff':
        request.session.flush()
        messages.error(request, "You do not have permission to view this page. Please login again")
        return redirect('login')
    
    # Get staff object
    try:
        staff_id = request.session.get('user_id')
        staff = STAFF.objects.get(id=staff_id)
    except STAFF.DoesNotExist:
        request.session.flush()
        messages.error(request, "Staff not found. Please login again.")
        return redirect('login')
    
    if request.method == 'POST':
        try:
            # Get form data
            category = request.POST.get('category')
            text = request.POST.get('text')
            attachment = request.FILES.get('attachment')
            
            # Validate required fields
            if not category or not text:
                messages.error(request, 'Please fill in all required fields.')
                return render(request, 'staff/submit_feedback.html', {'staff': staff})
            
            # Validate category
            valid_categories = ['Complaint', 'Feedback']
            if category not in valid_categories:
                messages.error(request, 'Please select a valid feedback category.')
                return render(request, 'staff/submit_feedback.html', {'staff': staff})
            
            # Validate text length
            if len(text.strip()) < 10:
                messages.error(request, 'Please provide at least 10 characters in your message.')
                return render(request, 'staff/submit_feedback.html', {'staff': staff})
            
            # Validate file size if attachment is provided
            if attachment:
                max_size = 5 * 1024 * 1024  # 5MB
                if attachment.size > max_size:
                    messages.error(request, 'File size must be less than 5MB.')
                    return render(request, 'staff/submit_feedback.html', {'staff': staff})
                
                # Validate file type
                allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.txt']
                file_name = attachment.name.lower()
                if not any(file_name.endswith(ext) for ext in allowed_extensions):
                    messages.error(request, 'Please upload a valid file type (PDF, DOC, DOCX, JPG, PNG, TXT).')
                    return render(request, 'staff/submit_feedback.html', {'staff': staff})
            
            # Create feedback record
            feedback = FEEDBACK(
                category=category,
                text=text.strip(),
                attachment=attachment,
                status='Unsolved'
            )
            feedback.save()
            
            # Success message
            feedback_type = "complaint" if category == "Complaint" else "feedback"
            messages.success(request, f'Your {feedback_type} has been submitted successfully. HR will review it and respond accordingly.')
            
            # Log the submission for debugging
            logging.info(f"Feedback submitted by staff {staff.id} ({staff.name}): Category={category}, ID={feedback.id}")
            
            # Redirect to prevent form resubmission
            return redirect('staff_submit_feedback')
            
        except Exception as e:
            # Log the error
            logging.error(f"Error submitting feedback for staff {staff.id}: {str(e)}")
            messages.error(request, 'An error occurred while submitting your feedback. Please try again.')
    
    # Render the form page
    return render(request, 'staff/submit_feedback.html', {'staff': staff})