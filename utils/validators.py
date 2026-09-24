"""
Validation Utilities Module
Handles strict data validation and formatting checks for registrations, logins, and complaints.
"""

import re
from email_validator import validate_email as validate_email_lib, EmailNotValidError
from config import get_config


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format and domain."""
    if not email:
        return False, "Email address is required"
    try:
        # validate and deliver parsed details
        validate_email_lib(email, check_deliverability=False)
        return True, ""
    except EmailNotValidError as e:
        return False, str(e)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password strength (min 8 chars, mixed case, number, and special character)."""
    min_len = 8

    if not password or len(password) < min_len:
        return False, f"Password must be at least {min_len} characters long"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character (e.g. !@#$%)"
        
    return True, ""


def validate_user_registration(data: dict) -> list[str]:
    """Validate user registration inputs."""
    config = get_config()
    errors = []

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    role = data.get('role', '').strip()
    department = data.get('department', '').strip() if role in ['admin', 'worker'] else None
    registration_number = data.get('registration_number', '').strip() if role == 'student' else None

    # Username validation
    if not username or len(username) < 3:
        errors.append('Username must be at least 3 characters long')
    elif not re.match(r"^[a-zA-Z0-9_-]+$", username):
        errors.append('Username can only contain alphanumeric characters, underscores, and hyphens')

    # Email validation
    is_valid_email, email_err = validate_email(email)
    if not is_valid_email:
        errors.append(email_err)

    # Password validation
    is_strong_pass, pass_err = validate_password_strength(password)
    if not is_strong_pass:
        errors.append(pass_err)

    if password != confirm_password:
        errors.append('Passwords do not match')

    # Role validation
    if not role or role not in config.VALID_ROLES:
        errors.append(f'Invalid role. Must be one of: {", ".join(config.VALID_ROLES)}')

    # Department validation for Admin/Worker
    if role in ['admin', 'worker']:
        if not department or department not in config.DEPARTMENTS:
            errors.append(f'A valid department is required for admins and workers. Choices: {", ".join(config.DEPARTMENTS)}')

    # Student registration number validation
    if role == 'student':
        if not registration_number:
            errors.append('Student Registration Number is mandatory')
        else:
            reg_num = registration_number.strip().upper()
            # Regex validation: SPTYYDDNNN
            if not re.match(r"^SPT\d{2}(CS|CE|EE|EC|ME|AD)\d{3}$", reg_num):
                errors.append('Registration number format is invalid. Format: SPTYYDDNNN (e.g. SPT24CS001)')
            else:
                # Check college registration database
                from database import CollegeStudent
                student = CollegeStudent.query.filter_by(registration_number=reg_num).first()
                if not student:
                    errors.append('Registration number is not registered in the college student database')

    return errors


def validate_complaint_data(data: dict) -> list[str]:
    """Validate complaint submission data."""
    config = get_config()
    errors = []

    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    category = data.get('category', '').strip()
    priority = data.get('priority', 'Low').strip()
    location = data.get('location', '').strip()

    if not title:
        errors.append('Complaint Title is required')
    elif len(title) > 200:
        errors.append('Title must not exceed 200 characters')

    if not description:
        errors.append('Complaint Description is required')
    elif len(description) > 5000:
        errors.append('Description must not exceed 5000 characters')

    if not category:
        errors.append('Complaint Category is required')
    elif category not in config.CATEGORY_ROUTING:
        errors.append('Invalid complaint category selected')

    if priority not in config.VALID_PRIORITIES:
        errors.append('Invalid priority selected')

    # Mandatory location validation
    if not location:
        errors.append('Location of the occurrence is mandatory')
    elif len(location) > 200:
        errors.append('Location detail must not exceed 200 characters')

    return errors


def validate_status_update(new_status: str) -> list[str]:
    """Validate status updates."""
    config = get_config()
    if new_status not in config.VALID_STATUSES:
        return [f'Invalid status update. Choose from: {", ".join(config.VALID_STATUSES)}']
    return []
