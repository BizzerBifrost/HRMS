from django.db import models
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
import datetime
import pytz


# Create your models here.

# staff
class STAFF(models.Model):
    id = models.TextField(primary_key=True, max_length=12)
    name = models.TextField(default='')
    position = models.TextField(default='')
    phone = models.TextField(default='')
    email = models.EmailField(default='')
    password = models.TextField(default='')
    STATUS = [ 
        ('',''),
        ('Married','married'),
        ('Single','single'),
    ]
    status = models.TextField(choices=STATUS, default='')
    GENDER = [
        ('',''),
        ('Male', 'male'),
        ('Female', 'female'),
    ]
    gender = models.TextField(choices=GENDER, default='')
    date_of_birth = models.DateField()
    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year
    
    bank_number = models.TextField(default='')
    emergency_contact = models.TextField(default='')

class EDUCATION(models.Model):
    id = models.AutoField(primary_key=True)
    certification = models.TextField()
    date_received = models.DateField()
    staffid = models.ForeignKey(STAFF, on_delete=models.CASCADE)

class EXPERIENCE(models.Model):
    id = models.AutoField(primary_key=True)
    detail = models.TextField()
    staffid = models.ForeignKey(STAFF, on_delete=models.CASCADE)

class ADDRESS(models.Model):
    id = models.AutoField(primary_key=True)
    address1 = models.TextField(default='')
    address2 = models.TextField(default='')
    poscode = models.IntegerField(default='')
    state = models.TextField(default='')
    staffid = models.ForeignKey(STAFF, on_delete=models.CASCADE)

class PAYROLL(models.Model):
    id = models.AutoField(primary_key=True)
    base = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pcb = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    epf_employer = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    epf_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    staffid = models.ForeignKey(STAFF, on_delete=models.CASCADE)
    
    # Use properties to calculate EPF values automatically
    @property
    def calculate_epf_employer(self):
        return (self.base + self.allowance + self.bonus) * Decimal('0.13')
    
    @property
    def calculate_epf_employee(self):
        return (self.base + self.allowance + self.bonus) * Decimal('0.11')
    
    @property
    def calculate_net_salary(self):
        return self.base + self.bonus + self.allowance - self.epf_employee - self.pcb
    
    def save(self, *args, **kwargs):
        self.epf_employer = self.calculate_epf_employer
        self.epf_employee = self.calculate_epf_employee
        self.net_salary = self.calculate_net_salary
        super().save(*args, **kwargs)

class FEEDBACK(models.Model):
    id = models.AutoField(primary_key=True)
    CATEGORY = [
        ('', ''),
        ('Complaint', 'complaint'),
        ('Feedback','feedback'),
    ]
    category = models.TextField(choices=CATEGORY, default='')
    text = models.TextField()
    attachment = models.FileField(upload_to='feedback_attachments/', blank=True, null=True)
    STATUS = [
        ('Unsolved','unsolved'),
        ('Solved','solved'),
    ]
    status = models.TextField(choices=STATUS, default='Unsolved')

class LEAVE_BALANCE(models.Model):
    id = models.AutoField(primary_key=True)
    staffid = models.OneToOneField(STAFF, on_delete=models.CASCADE, related_name='leave_balance')
    annual_leave = models.IntegerField(default=14)  
    leave_available = models.IntegerField(default=14)  
    year = models.IntegerField(default=datetime.datetime.now().year)  
    last_updated = models.DateTimeField(auto_now=True)  
    
    def reset_annual_leave(self):
        """Reset leave available to annual leave value if year has changed"""
        current_year = datetime.datetime.now().year
        if self.year < current_year:
            self.leave_available = self.annual_leave
            self.year = current_year
            self.save()
    
    def update_leave_available(self):
        """Update leave available based on approved time off requests"""
        # First check if we need to reset for a new year
        self.reset_annual_leave()
        
        # Calculate total approved days for current year
        approved_days = TIMEOFF.objects.filter(
            staffid=self.staffid,
            status='Approved',
            start__year=self.year
        ).aggregate(models.Sum('total_days'))['total_days__sum'] or 0
        
        # Update leave available
        self.leave_available = self.annual_leave - approved_days
        self.save()

# Modify the TIMEOFF save method to update leave balance when status changes
class TIMEOFF(models.Model):
    id = models.AutoField(primary_key=True)
    start = models.DateField()
    end = models.DateField()
    STATUS = [
        ('Pending', 'pending'),
        ('Approved', 'approved'),
        ('Denied','denied'),
    ]
    status = models.TextField(choices=STATUS, default='Pending')
    reason = models.TextField()
    total_days = models.IntegerField(default=0)
    staffid = models.ForeignKey(STAFF, on_delete=models.SET_NULL, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Calculate total days
        delta = self.end - self.start
        self.total_days = delta.days + 1
        
        # Check if this is a new record or status has changed to Approved
        is_new = self.pk is None
        
        if not is_new:
            old_instance = TIMEOFF.objects.get(pk=self.pk)
            status_changed = old_instance.status != self.status
        else:
            status_changed = False
        
        # Save the timeoff record
        super(TIMEOFF, self).save(*args, **kwargs)
        
        # Update leave balance if status changed to Approved
        if (is_new and self.status == 'Approved') or (status_changed and self.status == 'Approved'):
            # Get or create leave balance for staff
            leave_balance, created = LEAVE_BALANCE.objects.get_or_create(staffid=self.staffid)
            leave_balance.update_leave_available()
        # Also update if status changed from Approved to something else
        elif status_changed and old_instance.status == 'Approved':
            leave_balance, created = LEAVE_BALANCE.objects.get_or_create(staffid=self.staffid)
            leave_balance.update_leave_available()

# manager
class MANAGER(models.Model):
    id = models.TextField(primary_key=True)
    password = models.TextField(default='')
    staffid = models.ForeignKey(STAFF, on_delete=models.CASCADE)

class RECRUITMENT(models.Model):
    id = models.AutoField(primary_key=True)
    
    # Basic Information
    position = models.TextField(default='')
    reason = models.TextField(default='')
    total_personnel = models.IntegerField(default=1)
    
    # Status and Priority
    STATUS_CHOICES = [
        ('Pending', 'pending'),
        ('Under Review', 'under_review'),
        ('Approved', 'approved'),
        ('In Progress', 'in_progress'),
        ('Completed', 'completed'),
        ('Rejected', 'rejected'),
        ('On Hold', 'on_hold'),
        ('More Info Needed', 'more_info_needed'),
    ]
    status = models.TextField(choices=STATUS_CHOICES, default='Pending')
    
    PRIORITY_CHOICES = [
        ('Low', 'low'),
        ('Standard', 'standard'),
        ('High', 'high'),
        ('Urgent', 'urgent'),
        ('Critical', 'critical'),
    ]
    priority = models.TextField(choices=PRIORITY_CHOICES, default='Standard')
    
    # Timeline Information
    requested_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    target_start_date = models.DateField(null=True, blank=True)
    expected_completion_date = models.DateField(null=True, blank=True)
    
    TIMELINE_CHOICES = [
        ('1-2 weeks', '1-2 weeks'),
        ('2-4 weeks', '2-4 weeks'),
        ('1-2 months', '1-2 months'),
        ('2-3 months', '2-3 months'),
        ('3+ months', '3+ months'),
    ]
    expected_timeline = models.TextField(choices=TIMELINE_CHOICES, default='2-4 weeks')
    
    # Job Details
    job_description = models.TextField(blank=True, default='')
    required_qualifications = models.TextField(blank=True, default='')
    preferred_qualifications = models.TextField(blank=True, default='')
    salary_range_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_range_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    EMPLOYMENT_TYPE_CHOICES = [
        ('Full-time', 'full_time'),
        ('Part-time', 'part_time'),
        ('Contract', 'contract'),
        ('Temporary', 'temporary'),
        ('Internship', 'internship'),
    ]
    employment_type = models.TextField(choices=EMPLOYMENT_TYPE_CHOICES, default='Full-time')
    
    # Department and Location
    department = models.TextField(blank=True, default='')
    work_location = models.TextField(blank=True, default='')
    
    REMOTE_WORK_CHOICES = [
        ('On-site', 'on_site'),
        ('Remote', 'remote'),
        ('Hybrid', 'hybrid'),
    ]
    remote_work_option = models.TextField(choices=REMOTE_WORK_CHOICES, default='On-site')
    
    # Business Justification
    business_justification = models.TextField(blank=True, default='')
    budget_allocated = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    JUSTIFICATION_TYPE_CHOICES = [
        ('New Position', 'new_position'),
        ('Replacement', 'replacement'),
        ('Expansion', 'expansion'),
        ('Temporary Cover', 'temporary_cover'),
        ('Project Based', 'project_based'),
    ]
    justification_type = models.TextField(choices=JUSTIFICATION_TYPE_CHOICES, default='New Position')
    
    # Foreign Keys
    managerid = models.ForeignKey('MANAGER', on_delete=models.CASCADE)
    assigned_hr = models.ForeignKey('HR', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Tracking Information
    last_updated = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('HR', on_delete=models.SET_NULL, null=True, blank=True, related_name='recruitment_updates')
    
    # Additional Fields
    is_confidential = models.BooleanField(default=False)
    external_posting_allowed = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.position} - {self.total_personnel} positions (ID: {self.id})"
    
    @property
    def days_since_request(self):
        """Calculate days since the request was made"""
        return (timezone.now().date() - self.requested_date.date()).days
    
    @property
    def is_urgent(self):
        """Check if the request is urgent based on priority and time"""
        return self.priority in ['Urgent', 'Critical'] or self.days_since_request > 30
    
    @property
    def is_overdue(self):
        """Check if the expected completion date has passed"""
        if self.expected_completion_date:
            return self.expected_completion_date < timezone.now().date()
        return False
    
    class Meta:
        ordering = ['-requested_date']
        verbose_name = 'Recruitment Request'
        verbose_name_plural = 'Recruitment Requests'


class RECRUITMENT_NOTES(models.Model):
    """Model to track notes and comments on recruitment requests"""
    id = models.AutoField(primary_key=True)
    recruitment = models.ForeignKey(RECRUITMENT, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes')
    
    NOTE_TYPE_CHOICES = [
        ('HR Internal', 'hr_internal'),
        ('Manager Feedback', 'manager_feedback'),
        ('Status Update', 'status_update'),
        ('Interview Note', 'interview_note'),
        ('General', 'general'),
    ]
    note_type = models.TextField(choices=NOTE_TYPE_CHOICES, default='General')
    
    note_content = models.TextField()
    created_by = models.ForeignKey('HR', on_delete=models.SET_NULL, null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    is_visible_to_manager = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Note for {self.recruitment.position} - {self.note_type}"
    
    class Meta:
        ordering = ['-created_date']


class RECRUITMENT_STATUS_HISTORY(models.Model):
    """Model to track status changes in recruitment requests"""
    id = models.AutoField(primary_key=True)
    recruitment = models.ForeignKey(RECRUITMENT, on_delete=models.SET_NULL, null=True, blank=True, related_name='status_history')
    
    old_status = models.TextField(blank=True)
    new_status = models.TextField()
    changed_by = models.ForeignKey('HR', on_delete=models.SET_NULL, null=True, blank=True)
    changed_date = models.DateTimeField(auto_now_add=True)
    change_reason = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.recruitment.position} - {self.old_status} to {self.new_status}"
    
    class Meta:
        ordering = ['-changed_date']


class RECRUITMENT_ATTACHMENTS(models.Model):
    """Model to handle file attachments for recruitment requests"""
    id = models.AutoField(primary_key=True)
    recruitment = models.ForeignKey(RECRUITMENT, on_delete=models.SET_NULL, null=True, blank=True, related_name='attachments')
    
    file_name = models.TextField()
    file_path = models.FileField(upload_to='recruitment_attachments/', null=True, blank=True)
    uploaded_by = models.ForeignKey('HR', on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_date = models.DateTimeField(auto_now_add=True)
    
    ATTACHMENT_TYPE_CHOICES = [
        ('Job Description', 'job_description'),
        ('Budget Approval', 'budget_approval'),
        ('Organizational Chart', 'org_chart'),
        ('Supporting Document', 'supporting_doc'),
        ('Other', 'other'),
    ]
    attachment_type = models.TextField(choices=ATTACHMENT_TYPE_CHOICES, default='Other')
    
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.file_name} - {self.recruitment.position}"
    
    class Meta:
        ordering = ['-uploaded_date']


class TEAM(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.TextField(default='')
    managerid = models.ForeignKey('MANAGER', on_delete=models.CASCADE)

class TEAM_MEMBERSHIP(models.Model):
    team = models.ForeignKey(TEAM, on_delete=models.CASCADE, related_name='memberships')
    staff = models.ForeignKey('STAFF', on_delete=models.CASCADE)
    joined_date = models.DateField(auto_now_add=True)
    
    class Meta:
        unique_together = ('team', 'staff')  
        
    def __str__(self):
        return f"{self.staff} in {self.team}"


def get_malaysia_time():
    """Get current time in Malaysia timezone"""
    malaysia_tz = pytz.timezone('Asia/Kuala_Lumpur')
    return timezone.now().astimezone(malaysia_tz)

# Update your TEAM_GOALS model to ensure it uses Malaysia time properly:
class TEAM_GOALS(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.TextField(max_length=200)
    description = models.TextField()
    target_date = models.DateField()
    created_date = models.DateField(auto_now_add=True)
    
    STATUS_CHOICES = [
        ('Not Started', 'not_started'),
        ('In Progress', 'in_progress'),
        ('Completed', 'completed'),
        ('On Hold', 'on_hold'),
    ]
    status = models.TextField(choices=STATUS_CHOICES, default='Not Started')
    
    PRIORITY_CHOICES = [
        ('Low', 'low'),
        ('Medium', 'medium'),
        ('High', 'high'),
        ('Critical', 'critical'),
    ]
    priority = models.TextField(choices=PRIORITY_CHOICES, default='Medium')
    
    progress_percentage = models.IntegerField(default=0)  # 0-100
    notes = models.TextField(blank=True, default='')
    
    # Foreign key relationships
    team = models.ForeignKey(TEAM, on_delete=models.CASCADE, related_name='team_goals')
    created_by = models.ForeignKey(MANAGER, on_delete=models.CASCADE)
    
    # Metadata with timezone awareness
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.team.name if self.team.name else 'Team'}"
    
    @property
    def is_overdue(self):
        """Check if the goal is overdue"""
        # Use Malaysia timezone for comparison
        malaysia_tz = pytz.timezone('Asia/Kuala_Lumpur')
        today_malaysia = timezone.now().astimezone(malaysia_tz).date()
        return self.target_date < today_malaysia and self.status != 'Completed'
    
    @property
    def days_remaining(self):
        """Calculate days remaining until target date"""
        malaysia_tz = pytz.timezone('Asia/Kuala_Lumpur')
        today_malaysia = timezone.now().astimezone(malaysia_tz).date()
        delta = self.target_date - today_malaysia
        return delta.days
    
    class Meta:
        ordering = ['-created_date']
        verbose_name = 'Team Goal'
        verbose_name_plural = 'Team Goals'
# hr
class HR(models.Model):
    id = models.TextField(primary_key=True)
    password = models.TextField(default='')
    staffid = models.ForeignKey(STAFF, on_delete=models.CASCADE, default='')

class POLICIES(models.Model):
    id = models.AutoField(primary_key=True)
    policies = models.TextField()
    enacted = models.DateField(auto_now_add=True)

# admin
class ADMIN(models.Model):

    id = models.TextField(primary_key=True)
    name = models.TextField()
    password = models.TextField()