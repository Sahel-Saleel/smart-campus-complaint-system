"""
Authentication Routes Module
Handles user registration (disabled for students), login, logout,
forced first-time password changes, and password reset requests.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, g, flash, current_app
from flask_mail import Message
from datetime import datetime, timedelta
import logging
import random
import re

from database import db, User, CollegeStudent, PasswordResetRequest, Complaint, Upvote, Notification
from utils.decorators import login_required
from utils.security import hash_password, verify_password, is_bcrypt_hash
from utils.validators import validate_password_strength
from utils.helpers import extract_department_from_username, is_staff_username, is_student_username
from config import get_config

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def dispatch_otp_email(recipient_email, otp_code, user=None, subject="Your Campus Voice Login OTP"):
    """Render HTML email template and dispatch OTP message via Flask-Mail."""
    try:
        from app import mail
        html_body = render_template('email_otp.html', otp=otp_code, user=user)
        sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME') or 'noreply@campusvoice.edu'

        msg = Message(
            subject=subject,
            recipients=[recipient_email],
            html=html_body,
            sender=sender
        )

        mail_user = current_app.config.get('MAIL_USERNAME')
        mail_pass = current_app.config.get('MAIL_PASSWORD')

        if mail_user and mail_pass:
            mail.send(msg)
            logger.info(f"Dispatched OTP email via Flask-Mail to {recipient_email}")
        else:
            logger.warning(f"MAIL_USERNAME and MAIL_PASSWORD are not set in .env. Email to {recipient_email} could not be sent.")
            flash(f"⚠️ SMTP credentials (MAIL_USERNAME/MAIL_PASSWORD) are missing in .env. Please configure email settings to receive actual emails.", "warning")
        return True
    except Exception as e:
        logger.error(f"Failed to dispatch OTP email to {recipient_email}: {e}", exc_info=True)
        flash(f"⚠️ Email delivery failed ({e}). Please check your SMTP settings in .env.", "warning")
        return False


def dispatch_onboarding_complete_email(user):
    """Render HTML confirmation email and send email linked / onboarding complete notification via Flask-Mail."""
    if not user or not user.email or user.email.endswith('@pending.college.edu'):
        return False

    try:
        from app import mail
        completion_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        html_body = render_template('email_onboarding_complete.html', user=user, time=completion_time)
        sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME') or 'noreply@campusvoice.edu'

        msg = Message(
            subject="Account Setup Complete: Email Linked Successfully - Campus Voice",
            sender=sender,
            recipients=[user.email],
            body=f"Hello {user.username},\n\nYour account setup for Campus Voice has been completed and your email address {user.email} has been linked to your account.\n\nThank you,\nCampus Voice Administration",
            html=html_body
        )

        mail_user = current_app.config.get('MAIL_USERNAME')
        mail_pass = current_app.config.get('MAIL_PASSWORD')
        if mail_user and mail_pass:
            mail.send(msg)
            logger.info(f"Dispatched email linked / onboarding completion email to {user.email}")
            print(f"SUCCESS: Onboarding completion email delivered to {user.email}")
        else:
            logger.info(f"Onboarding completion email generated for {user.username} ({user.email}) [SMTP credentials not set]")
        return True
    except Exception as e:
        logger.error(f"Failed to send onboarding completion email: {e}")
        print(f"FAILED: Onboarding completion email failed: {e}")
        flash(f"Debug: Email notification failed to send. Error: {str(e)}", "warning")
        return False


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and user authentication handler with brute-force protection."""
    if request.method == 'GET':
        if 'user_id' not in session:
            session.pop('change_password_required', None)
            return render_template('login.html')

        if not session.get('change_password_required'):
            user = User.query.get(session['user_id'])
            if user:
                role_redirects = {
                    'worker': 'complaints.worker_dashboard',
                    'admin': 'admin.dashboard',
                    'principal': 'principal.dashboard',
                    'staff': 'complaints.student_dashboard',
                    'student': 'complaints.student_dashboard'
                }
                return redirect(url_for(role_redirects.get(user.role, 'home')))
        return render_template('login.html')
    config = get_config()
    data = request.form
    username = data.get('username', '').upper().strip()
    password = data.get('password', '')
    selected_role = data.get('role', '').strip()

    # Base checks
    errors = []
    if not username:
        errors.append('Username is required')
    if not password:
        errors.append('Password is required')
    if not selected_role or selected_role not in config.VALID_ROLES:
        errors.append('Please select a valid role')

    if errors:
        return render_template('login.html', errors=errors), 400

    # --- Unified Account Existence & Password Validation ---
    reg_num_or_username = username

    user = User.query.filter(
        (db.func.lower(User.username) == reg_num_or_username.lower()) |
        (db.func.lower(User.registration_number) == reg_num_or_username.lower())
    ).first()

    def is_role_compatible(user_role, sel_role):
        if user_role == sel_role:
            return True
        if user_role in ['staff', 'admin', 'hod', 'principal', 'worker'] and sel_role in ['staff', 'admin', 'hod', 'principal', 'worker', 'maintenance_worker']:
            return True
        return False

    # 1. Non-existent Account Check
    if not user or not is_role_compatible(user.role, selected_role):
        if selected_role == 'student':
            flash("Register number not accepted. Please ensure your HOD has added you to the system.", "danger")
        else:
            flash("Account not found. Please ensure the Admin or HOD has added you to the system.", "danger")
        return redirect(url_for('auth.login'))

    # Update department if missing for existing student
    if user.role == 'student' and not user.department:
        user.department = extract_department_from_username(user.username)
        db.session.commit()

    utc_now = datetime.utcnow()
    if user.locked_until and user.locked_until > utc_now:
        lock_remaining = max(1, int((user.locked_until - utc_now).total_seconds() / 60))
        flash(f"Account locked. Try again in {lock_remaining} minutes.", "danger")
        return redirect(url_for('auth.login'))

    if not user.active:
        flash("Your account has been deactivated", "danger")
        return redirect(url_for('auth.login'))

    # 2. Incorrect Password Check
    if not verify_password(password, user.password) and not verify_password(password.upper(), user.password):
        user.login_attempts += 1
        if user.login_attempts >= config.MAX_LOGIN_ATTEMPTS:
            user.locked_until = utc_now + timedelta(minutes=config.ACCOUNT_LOCKOUT_MINUTES)
            flash(f"Invalid password. Account locked for {config.ACCOUNT_LOCKOUT_MINUTES} minutes.", "danger")
        else:
            flash("Invalid password. Please try again.", "danger")
        db.session.commit()
        return redirect(url_for('auth.login'))

    # Transparent migration for old non-bcrypt hashed passwords
    if not is_bcrypt_hash(user.password):
        try:
            user.password = hash_password(password)
            if user.password_changed_at is not None:
                user.password_changed_at = utc_now
        except Exception as e:
            logger.error(f"Failed to migrate password hash: {e}")

    # Successful authentication: Reset locking & set session
    user.login_attempts = 0
    user.locked_until = None
    user.last_login = utc_now
    db.session.commit()

    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session.permanent = True

    # Redirect to first-time onboarding setup if password has not been changed
    if user.is_first_login or user.password_changed_at is None:
        session['change_password_required'] = True
        logger.info(f"User {user.username} logged in for the first time. Redirecting to onboarding setup.")
        return redirect(url_for('auth.change_password'))

    logger.info(f"User {user.username} login success.")

    print(f"\n--- DEBUG: LOGIN TRIGGERED FOR {user.username} ---")
    print(f"Role in DB: '{user.role}'")
    print(f"Email in DB: '{user.email}'")

    # Ensure the check is robust
    role_is_valid = bool(user.role and user.role.lower() in ['admin', 'hod', 'principal'])
    email_is_valid = bool(user.email and user.email.strip())

    print(f"Role is valid for email: {role_is_valid}")
    print(f"Email is present: {email_is_valid}")

    if role_is_valid and email_is_valid:
        print("Attempting to send email now...")
        try:
            from app import mail
            login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME') or 'noreply@campusvoice.edu'
            try:
                html_body = render_template('email_login_alert.html', user=user, time=login_time)
            except Exception as tmpl_err:
                html_body = None
                print(f"Template load notice: {tmpl_err}")

            msg = Message(
                subject="Security Alert: New Login to Campus Voice",
                sender=sender,
                recipients=[user.email],
                body=f"Hello {user.username},\n\nA new login was detected on your account at {login_time}.\nIf this was you, no action is needed.",
                html=html_body
            )
            mail.send(msg)
            print("SUCCESS: Email sent perfectly!")
            logger.info(f"Dispatched login alert email to {user.email}")
        except Exception as e:
            print(f"FAILED: Email crashed with error: {str(e)}")
            logger.error(f"Failed to send login alert email: {e}")
            flash(f"Email Error: {str(e)}", "danger")
    else:
        print("SKIPPED: Did not send email because Role or Email check failed.")
    print("---------------------------------------------------\n")

    role_redirects = {
        'worker': 'complaints.worker_dashboard',
        'admin': 'admin.dashboard',
        'principal': 'principal.dashboard',
        'staff': 'complaints.student_dashboard',
        'student': 'complaints.student_dashboard'
    }
    return redirect(url_for(role_redirects.get(user.role, 'home')))


@auth_bp.route('/login-verify-otp', methods=['GET', 'POST'])
def verify_login_otp():
    """Verify Email OTP for Admin, HOD, Principal, Worker, and Staff login."""
    user_id = session.get('login_otp_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get_or_404(user_id)
    email = session.get('login_otp_email', user.email)
    demo_otp = session.get('login_otp_code')
    expiry_str = session.get('login_otp_expiry')

    if request.method == 'GET':
        return render_template('verify_login_otp.html', user=user, email=email)

    otp_entered = request.form.get('otp_code', '').strip()
    errors = []

    # Expiry check
    if expiry_str:
        try:
            expiry_dt = datetime.fromisoformat(expiry_str)
            if datetime.utcnow() > expiry_dt:
                errors.append("OTP code has expired. Please click 'Resend OTP Code'.")
        except Exception:
            pass

    if not demo_otp or otp_entered != str(demo_otp).strip():
        errors.append("Invalid OTP code. Please check and try again.")

    if errors:
        return render_template('verify_login_otp.html', user=user, email=email, errors=errors), 400

    # Successful OTP authentication
    session.pop('login_otp_user_id', None)
    session.pop('login_otp_code', None)
    session.pop('login_otp_email', None)
    session.pop('login_otp_expiry', None)

    utc_now = datetime.utcnow()
    user.login_attempts = 0
    user.locked_until = None
    user.last_login = utc_now
    db.session.commit()

    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session.permanent = True

    if user.password_changed_at is None:
        session['change_password_required'] = True
        logger.info(f"Staff/Admin user {user.username} authenticated via OTP with default password. Redirecting to change password onboarding.")
        return redirect(url_for('auth.change_password'))

    logger.info(f"Staff/Admin user {user.username} login success via Email OTP.")
    role_redirects = {
        'worker': 'complaints.worker_dashboard',
        'admin': 'admin.dashboard',
        'principal': 'principal.dashboard',
        'staff': 'complaints.student_dashboard'
    }
    return redirect(url_for(role_redirects.get(user.role, 'home')))


@auth_bp.route('/resend-login-otp', methods=['GET'])
def resend_login_otp():
    """Resend a new Login OTP code."""
    user_id = session.get('login_otp_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('auth.login'))

    otp_code = f"{random.randint(100000, 999999)}"
    session['login_otp_code'] = otp_code
    session['login_otp_expiry'] = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    recipient_email = session.get('login_otp_email', user.email)

    logger.info(f"Resent Login OTP for {user.role.upper()} {user.username} ({recipient_email}): {otp_code}")
    dispatch_otp_email(recipient_email, otp_code, user=user, subject="Your Campus Voice Login OTP (Resent)")
    flash(f"A new OTP code has been sent to {recipient_email}.", "success")
    return redirect(url_for('auth.verify_login_otp'))



@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page is disabled in favor of Registration Number login."""
    return render_template('error.html', error='Direct registration is disabled. Students must log in using their Registration Number.'), 403


@auth_bp.route('/first-login', methods=['GET', 'POST'])
@auth_bp.route('/first_login', methods=['GET', 'POST'])
@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """Allows authenticated users to change their password or forces first-time password change."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('auth.login'))

    current_user = g.current_user if (hasattr(g, 'current_user') and g.current_user) else user

    is_forced_first_login = session.get('change_password_required', False) or user.password_changed_at is None

    if request.method == 'GET':
        return render_template('change_password.html', user=user, is_forced_first_login=is_forced_first_login)

    data = request.form
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()

    errors = []

    # If first-time login onboarding, collect personal profile details
    if is_forced_first_login:
        if current_user.role in ['admin', 'hod', 'principal']:
            logger.info(f"First login onboarding for role '{current_user.role}' (user: {current_user.username}).")
        if not full_name:
            errors.append('Full Name is required for first-time account setup')
        if not email:
            errors.append('Email Address is required for first-time account setup')
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('Please enter a valid email address')
        else:
            # Check email uniqueness against other accounts
            existing_user = User.query.filter(User.email == email, User.id != user.id).first()
            if existing_user:
                errors.append('This email address is already registered to another user')
    else:
        if not current_password:
            errors.append('Current password is required')
        elif not verify_password(current_password, user.password):
            errors.append('Current password is incorrect')

    if new_password != confirm_password:
        errors.append('New passwords do not match')

    is_strong, strength_err = validate_password_strength(new_password)
    if not is_strong:
        errors.append(strength_err)

    # Prevent reusing default password if student registration number exists
    if user.registration_number and new_password.upper() == user.registration_number.upper():
        errors.append('New password cannot be the same as your registration number')

    if errors:
        return render_template('change_password.html', user=user, errors=errors, is_forced_first_login=is_forced_first_login), 400

    try:
        user.password = hash_password(new_password)
        user.password_changed_at = datetime.utcnow()

        if is_forced_first_login:
            user.full_name = full_name
            user.email = email
            user.phone = phone
            user.is_first_login = False

        db.session.commit()

        session.pop('change_password_required', None)
        logger.info(f"User {user.username} completed onboarding and updated password successfully.")

        if is_forced_first_login:
            dispatch_onboarding_complete_email(user)
        
        flash("Account setup and password update completed successfully!", "success")
        if user.role in ['student', 'staff']:
            return redirect(url_for('complaints.student_dashboard'))
        elif user.role == 'principal':
            return redirect(url_for('principal.dashboard'))
        elif user.role in ['admin', 'hod']:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('auth.profile'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error completing onboarding: {e}", exc_info=True)
        return render_template('change_password.html', user=user, errors=['Failed to complete setup. Try again.'], is_forced_first_login=is_forced_first_login), 500


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Allows users to request a password reset. Admins/HODs/Principal/Staff verify via Email OTP, students via Admin approval."""
    if request.method == 'GET':
        return render_template('forgot_password.html')

    registration_number = request.form.get('registration_number', '').strip()
    if not registration_number:
        return render_template('forgot_password.html', errors=['Registration Number, Username, or Email is required']), 400

    # Look up user by email, registration_number, or username
    user = User.query.filter(
        (db.func.lower(User.email) == registration_number.lower()) |
        (db.func.lower(User.registration_number) == registration_number.lower()) |
        (db.func.lower(User.username) == registration_number.lower())
    ).first()

    # Case: User record not found in system
    if not user:
        student_record = CollegeStudent.query.filter(
            db.func.lower(CollegeStudent.registration_number) == registration_number.lower()
        ).first()
        if student_record:
            return render_template('forgot_password.html', info_message='Your account has not been activated yet. Please log in using your Registration Number as both the username and password.'), 200

        return render_template('forgot_password.html', errors=['Invalid Registration Number, Username, or Email. User not found.']), 403

    # Check if user has an email on file
    if not user.email:
        return render_template('forgot_password.html', errors=['No registered email address found for this account. Please contact an Administrator.']), 400

    # For Admins, HODs, Principal, Workers, and Staff: Generate 6-digit Email OTP code for direct self-reset
    if user.role in ['admin', 'hod', 'principal', 'worker', 'staff']:
        otp_code = f"{random.randint(100000, 999999)}"
        otp_expiry = datetime.utcnow() + timedelta(minutes=15)

        existing_req = PasswordResetRequest.query.filter_by(user_id=user.id, status='Pending').first()
        if existing_req:
            existing_req.otp_code = otp_code
            existing_req.otp_expiry = otp_expiry
        else:
            new_req = PasswordResetRequest(user_id=user.id, status='Pending', otp_code=otp_code, otp_expiry=otp_expiry)
            db.session.add(new_req)

        db.session.commit()
        session['reset_user_id'] = user.id
        logger.info(f"Password Reset OTP generated for {user.role.upper()} {user.username} ({user.email}): {otp_code}")
        dispatch_otp_email(user.email, otp_code, user=user, subject="Your Campus Voice Password Reset OTP")

        return render_template('verify_otp.html', user=user, info_message=f"An OTP verification code has been sent to {user.email}.")

    # For Students: Create Admin Approval request
    existing_request = PasswordResetRequest.query.filter_by(user_id=user.id, status='Pending').first()
    if existing_request:
        return render_template('forgot_password.html', info_message='A password reset request is already pending administrator approval.'), 200

    try:
        reset_request = PasswordResetRequest(user_id=user.id, status='Pending')
        db.session.add(reset_request)

        # Notify system administrators about the student reset request
        admin_users = User.query.filter(User.role.in_(['admin', 'principal'])).all()
        for admin_user in admin_users:
            if admin_user.id != user.id:
                notif = Notification(
                    recipient_id=admin_user.id,
                    notification_type='system',
                    title=f"🔑 Student Password Reset Request: {user.username}",
                    message=f"Student {user.full_name or user.username} requested a password reset.",
                    is_read=False
                )
                db.session.add(notif)

        db.session.commit()
        logger.info(f"Student password reset request created for user: {user.username}")
        return render_template('forgot_password.html', success_message='Password reset request submitted successfully for Administrator approval.'), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error requesting password reset: {e}", exc_info=True)
        return render_template('forgot_password.html', errors=['System error submitting request. Try again later.']), 500


@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """Verify Email OTP code and reset password for Admins, HODs, Workers, and Staff."""
    user_id = session.get('reset_user_id')
    if not user_id:
        return redirect(url_for('auth.forgot_password'))

    user = User.query.get_or_404(user_id)
    req = PasswordResetRequest.query.filter_by(user_id=user.id, status='Pending').order_by(PasswordResetRequest.created_at.desc()).first()

    if request.method == 'GET':
        return render_template('verify_otp.html', user=user)

    otp_entered = request.form.get('otp_code', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    errors = []
    if not req or not req.is_otp_valid(otp_entered):
        errors.append("Invalid or expired OTP code. Please check the code and try again.")
    
    if len(new_password) < 6:
        errors.append("New password must be at least 6 characters long.")

    if new_password != confirm_password:
        errors.append("Passwords do not match.")

    # Check if the new password matches the current/old password
    if verify_password(new_password, user.password):
        errors.append("You cannot reuse your old password. Please choose a different one.")

    if errors:
        return render_template('verify_otp.html', user=user, errors=errors), 400

    try:
        user.password = hash_password(new_password)
        user.password_changed_at = datetime.utcnow()
        req.status = 'Verified'
        db.session.commit()
        session.pop('reset_user_id', None)
        logger.info(f"Password reset successfully via OTP for user: {user.username}")
        flash("Your password has been successfully reset! Please log in with your new password.", "success")
        return redirect(url_for('auth.login'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error completing OTP password reset: {e}", exc_info=True)
        return render_template('verify_otp.html', user=user, errors=['System error updating password. Try again.']), 500


@auth_bp.route('/logout')
def logout():
    """Logout current user and invalidate the session."""
    username = session.get('username')
    session.clear()
    logger.info(f"User logged out: {username}")
    return redirect(url_for('auth.login'))


# ========== AJAX JSON VALIDATION API ENDPOINTS ==========

@auth_bp.route('/api/v1/check-username', methods=['POST'])
@auth_bp.route('/api/check-username', methods=['POST'])
def check_username_availability():
    """Disabled since students do not register manually."""
    return jsonify({'available': False, 'message': 'Registration is managed by Registration Numbers'})


@auth_bp.route('/api/v1/check-email', methods=['POST'])
@auth_bp.route('/api/check-email', methods=['POST'])
def check_email_availability():
    """Disabled since students do not register manually."""
    return jsonify({'available': False, 'message': 'Registration is managed by Registration Numbers'})


# ========== USER PROFILE ROUTE ==========
@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page displaying details, statistics, and editable phone number."""
    user = g.current_user

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        if not email:
            flash("Email address is required.", "error")
            return redirect(url_for('auth.profile'))

        # Check if email is already in use by another user
        existing_user = User.query.filter(User.email == email, User.id != user.id).first()
        if existing_user:
            flash("Email address is already in use by another user.", "error")
            return redirect(url_for('auth.profile'))

        user.full_name = full_name
        user.email = email
        user.phone = phone
        try:
            db.session.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating profile: {e}", exc_info=True)
            flash("Failed to update profile.", "error")
        return redirect(url_for('auth.profile'))

    # Calculate user statistics
    complaints_count = Complaint.query.filter_by(user_id=user.id).count()
    upvotes_count = Upvote.query.filter_by(user_id=user.id).count()

    stats = {
        'complaints_submitted': complaints_count,
        'upvotes_given': upvotes_count
    }

    return render_template(
        'profile.html',
        user=user,
        stats=stats
    )

