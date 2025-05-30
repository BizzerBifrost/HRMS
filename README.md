# Human Resources Management System (HRMS) for KOOP-KPMIM

A comprehensive web-based Human Resources Management System built with Django framework for KOOP-KPMIM (Kolej Profesional MARA Indera Mahkota Cooperative).

![System Status](https://img.shields.io/badge/Status-Active-green)
![Framework](https://img.shields.io/badge/Framework-Django-092E20)
![License](https://img.shields.io/badge/License-Proprietary-red)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [User Roles](#user-roles)
- [System Architecture](#system-architecture)
- [Color Scheme](#color-scheme)
- [Usage](#usage)
- [Security Features](#security-features)
- [Contributing](#contributing)
- [License](#license)

## Overview

The HRMS for KOOP-KPMIM is designed to digitize HR operations, replacing manual reporting with an efficient online platform. The system serves multiple user types including employees, managers, HR staff, and administrators, providing role-based access to various HR functions.

### Project Goals
- Transform manual HR processes into digital workflows
- Enhance transparency and communication across departments
- Reduce administrative workload and minimize errors
- Improve data accuracy and accessibility
- Support KOOP-KPMIM's vision of being "Trustworthy, Progressive, and Professional"

## Features

### For All Users
- **Secure Authentication**: Role-based login system with password strength validation
- **Responsive Design**: Works on desktop and mobile devices
- **Popup Animations**: Welcome animations for enhanced user experience
- **Company Policies**: View current organizational policies and procedures

### For Staff Members
- **Personal Profile Management**: Update personal information and contact details
- **Leave Application**: Submit time-off requests with automatic balance checking
- **Leave Status Tracking**: View application history and current status
- **Pay Slip Access**: Download monthly pay slips in PDF format
- **Feedback Submission**: Submit complaints or feedback to HR
- **Team Goals**: View departmental objectives set by managers

### For Managers
- **Leave Approvals**: Review and approve/deny team member leave requests
- **Team Management**: Oversee team members and their information
- **Goal Setting**: Set departmental objectives and KPIs
- **Recruitment Requests**: Submit new hire requisitions to HR
- **Team Dashboard**: Monitor team performance and metrics

### For HR Staff
- **Employee Management**: Register, update, and manage all employee records
- **Payroll Processing**: Set up and manage salary information for all staff
- **Policy Management**: Create, update, and publish company policies
- **Recruitment Oversight**: Process manager recruitment requests
- **Feedback Management**: Handle employee complaints and feedback
- **Leave Balance Management**: Set and adjust employee leave entitlements

### For Administrators
- **User Management**: Create and manage all system users across roles
- **System Configuration**: Configure system settings and permissions
- **Data Oversight**: Monitor system usage and data integrity

## System Requirements

### Minimum Hardware Requirements
- **Processor**: Dual-core processor with 1GHz clock speed
- **Memory**: 4GB RAM minimum
- **Storage**: 512GB SSD
- **Network**: Internet connection required
- **Monitor**: 60Hz refresh rate minimum

### Software Requirements
- **Operating System**: Windows 11 Home 64-Bit (primary), macOS 12.0+, or Ubuntu 22.04 LTS
- **Web Browser**: Chrome, Firefox, or Edge (latest versions)
- **Python**: 3.13.1 (64-Bit)
- **Node.js**: v22.15.0 LTS
- **Database**: SQLite (default) or PostgreSQL/MySQL for production

### Development Tools
- **Code Editor**: Visual Studio Code
- **Version Control**: Git 2.49.0 + GitHub Desktop
- **Design Tool**: Figma for UI/UX design
- **Framework**: Django (latest stable version)

## Installation

### Prerequisites
1. Install Python 3.13.1
2. Install Node.js v22.15.0 LTS
3. Install Git
4. Install Visual Studio Code (recommended)

### Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-organization/hrms-koop-kpmim.git
   cd hrms-koop-kpmim
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv hrms_env
   
   # Windows
   hrms_env\Scripts\activate
   
   # macOS/Linux
   source hrms_env/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -m requirements.txt
   pip install django
   pip install pillow  # For image handling
   # Add other required packages
   ```

4. **Database Setup**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create Superuser** (Optional)
   ```bash
   python manage.py createsuperuser
   ```

6. **Collect Static Files**
   ```bash
   python manage.py collectstatic
   ```

7. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

8. **Access the Application**
   Open your browser and navigate to `http://localhost:8000`

## User Roles

### Staff (`/staff/`)
- Personal information management
- Leave applications and tracking
- Pay slip access
- Feedback submission

### Manager (`/manager/`)
- Team leave approvals
- Goal setting for team
- Recruitment requests
- Team oversight

### HR (`/hr/`)
- Employee lifecycle management
- Payroll administration
- Policy management
- Recruitment processing
- Feedback handling

### Administrator (`/administrator/`)
- User account management
- System configuration
- Access control
- System monitoring

## System Architecture

### Database Models
- **STAFF**: Employee information and authentication
- **MANAGER**: Manager-specific data linked to staff
- **HR**: HR personnel data linked to staff
- **ADMIN**: Administrator accounts
- **PAYROLL**: Salary and compensation information
- **TIMEOFF**: Leave applications and approvals
- **LEAVE_BALANCE**: Employee leave entitlements
- **POLICIES**: Company policies and procedures
- **FEEDBACK**: Employee feedback and complaints
- **RECRUITMENT**: Hiring requests from managers
- **TEAM**: Team structure and management

## Color Scheme

The system follows a consistent color palette:

- **Primary Color**: `#F0F0F0` (Light Gray Background)
- **Secondary Color**: `#0053ED` (Blue - Headers, Buttons)
- **Accent Color**: `#E90000` (Red - Alerts, Important Actions)
- **Text Color**: `#4A4A4A` (Dark Gray)
- **Header**: `#0053ED` (Blue)
- **Footer**: `#4A4A4A` (Dark Gray)

## Usage

### Getting Started
1. Access the system through your web browser
2. Login with your assigned credentials
3. Complete the welcome popup tutorial
4. Navigate using the dashboard cards
5. Use the dropdown menu (user image) for profile and logout options

### Logo Functionality
The logo in the header serves as a navigation element:
- **Not logged in**: Returns to index page
- **Staff user**: Returns to staff dashboard
- **Manager user**: Returns to manager dashboard
- **HR user**: Returns to HR dashboard  
- **Admin user**: Returns to admin dashboard

### Password Requirements
All passwords must meet these criteria:
- Minimum 8 characters
- At least one uppercase letter
- At least one number
- At least one special character
- Real-time strength indicator (Weak/Medium/Strong)

## Security Features

- **Password Hashing**: All passwords are securely hashed using Django's built-in functions
- **Session Management**: Secure session handling with automatic timeouts
- **Role-based Access Control**: Users can only access authorized pages
- **Input Validation**: Form inputs are validated both client-side and server-side
- **CSRF Protection**: Cross-Site Request Forgery protection enabled
- **Unique ID Validation**: Prevents duplicate user IDs across all user types


## Contributing

This is a proprietary system developed for KOOP-KPMIM. Internal contributions should follow these guidelines:

1. **Code Standards**: Follow PEP 8 for Python code
2. **Documentation**: Update documentation for any new features
3. **Testing**: Test all functionality before committing
4. **Security**: Never commit sensitive information like passwords or API keys


## Support

For technical support or questions about the system:

- **Internal IT Support**: Contact your system administrator
- **System Issues**: Report through the internal feedback system

## License

This project is proprietary software developed specifically for KOOP-KPMIM (Kolej Profesional MARA Indera Mahkota Cooperative). All rights reserved.

**© 2025 KOOP-KPMIM Human Resources Management System | All Rights Reserved**

---

### Project Information
- **Academic Session**: Session 1/2025
- **Course**: CSC2764 - Project Design Implementation and Evaluation
- **Institution**: Kolej Profesional MARA Indera Mahkota
- **Developer**: Asmawi Aiman Mohd Sani
- **Client**: KOOP-KPMIM

---

*This system was developed as part of an academic project to demonstrate comprehensive system development capabilities including feasibility studies, project planning, quality assurance, and full-stack web development.*