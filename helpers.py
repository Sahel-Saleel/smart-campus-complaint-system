from flask import jsonify, has_request_context
from datetime import datetime
import logging
from utils.security import verify_password as verify_pwd_security
from database import db, User, Complaint, Upvote, Notification, AuditLog

logger = logging.getLogger(__name__)

def api_response(success: bool, data=None, message: str = "", errors=None, status_code: int = 200):
    """Return a standardized JSON API response envelope with backward compatibility."""
    payload = {
        'success': success,
        'data': data if data is not None else {},
        'message': message,
        'error': message if not success else None,  # for legacy template alerts
        'errors': errors if errors is not None else [],
        'meta': {
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'version': 'v1'
        }
    }
    return jsonify(payload), status_code

# ========== PASSWORD HELPERS ==========
def verify_password(hashed_password, password):
    """Verify a password against its hash using security utility."""
    return verify_pwd_security(password, hashed_password)

import re

# ========== USERNAME VALIDATION HELPERS ==========
def is_teaching_staff_username(username):
    """
    Check if username follows Teaching Staff (TS) format: 'TS' followed by 3 digits (e.g., TS182, TS057).
    """
    if not username:
        return False
    return bool(re.match(r'^TS\d{3}$', username.strip(), re.IGNORECASE))

def is_non_teaching_staff_username(username):
    """
    Check if username follows Non-Teaching Staff (NT) format (Electrical/Plumbing, Maintenance): 'NT' followed by 3 digits (e.g., NT069, NT001).
    """
    if not username:
        return False
    return bool(re.match(r'^NT\d{3}$', username.strip(), re.IGNORECASE))

def is_staff_username(username):
    """
    Check if username follows any staff format: TS (Teaching Staff) or NT (Non-Teaching Staff) followed by 3 digits.
    """
    if not username:
        return False
    return bool(re.match(r'^(TS|NT)\d{3}$', username.strip(), re.IGNORECASE))

def is_student_username(username):
    """
    Check if username follows student format (starting with SPT or LSPT followed by year, branch code, and digits).
    """
    if not username:
        return False
    return bool(re.match(r'^(SPT|LSPT)\d{2}(CS|CE|EE|EC|ME|AD)\d{3}$', username.strip(), re.IGNORECASE))

# ========== DEPARTMENT MAPPING & PARSING ==========
DEPT_MAP = {
    'CS': 'Computer Science Engineering',
    'ME': 'Mechanical Engineering',
    'CE': 'Civil Engineering',
    'EE': 'Electrical Engineering',
    'EC': 'Electronics Engineering',
    'AD': 'Artificial Intelligence and Data Science'
}

def extract_department_from_username(username):
    """
    Extract student's official branch department name from their username/registration number.
    Handles 'SPT' and 'LSPT' formats by extracting code before last 3 digits.
    Example: SPT24CS092 -> CS -> Computer Science Engineering
    """
    if not username or len(username) < 5:
        return 'Unknown Department'
    dept_code = username[-5:-3].upper()
    return DEPT_MAP.get(dept_code, 'Unknown Department')

# ========== ROUTING HELPERS ==========
CATEGORY_ROUTING = {
    'Electrical/Plumbing': 'Electrical/Plumbing',
    'Hostel': 'Hostel',
    'Academic/General': 'Academic/General',
    'Ragging': 'Principal',  # Special: goes to Principal only
    'Drug Abuse': 'Principal'  # Special: goes to Principal only
}

CONFIDENTIAL_CATEGORIES = ['Ragging', 'Drug Abuse']

def get_route_department(category):
    """Get the department to route complaint to"""
    return CATEGORY_ROUTING.get(category, None)

def is_category_confidential(category):
    """Check if category should be confidential"""
    return category in CONFIDENTIAL_CATEGORIES

def cleanup_old_archives():
    """Permanently delete complaints resolved more than 14 days ago."""
    from datetime import timedelta
    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
    old_resolved = Complaint.query.filter(
        Complaint.status == 'Resolved',
        Complaint.resolved_at != None,
        Complaint.resolved_at < fourteen_days_ago
    ).all()

    if old_resolved:
        count = len(old_resolved)
        for complaint in old_resolved:
            db.session.delete(complaint)
        db.session.commit()
        return count
    return 0

def route_complaint_to_admin(complaint):
    """Route complaint to appropriate admin based on category"""
    category = complaint.category
    department_name = get_route_department(category)

    if not department_name or department_name == 'Principal':
        # These go directly to principal, no admin assignment
        complaint.is_confidential = True
        return None

    # Find admin for this department
    admin = User.query.filter_by(
        role='admin',
        department=department_name,
        active=True
    ).first()

    if admin:
        complaint.assigned_to = admin.id
        return admin

    return None

# ========== NOTIFICATION HELPERS ==========
def create_notification(recipient_id, notification_type, title, message, complaint_id=None):
    """Create a notification for a user"""
    notification = Notification(
        recipient_id=recipient_id,
        complaint_id=complaint_id,
        notification_type=notification_type,
        title=title,
        message=message,
        is_read=False
    )
    db.session.add(notification)
    db.session.commit()
    return notification

def notify_department_on_complaint(complaint):
    """Notify department/admin when new complaint is submitted"""
    if complaint.is_confidential:
        # Notify all principals
        principals = User.query.filter_by(role='principal', active=True).all()
        for principal in principals:
            create_notification(
                recipient_id=principal.id,
                notification_type='new_complaint',
                title=f'New Confidential Complaint: {complaint.category}',
                message=f'A new {complaint.category} complaint has been submitted',
                complaint_id=complaint.id
            )
    else:
        # Notify assigned admin
        if complaint.assigned_to:
            assigned_admin = User.query.get(complaint.assigned_to)
            if assigned_admin:
                create_notification(
                    recipient_id=assigned_admin.id,
                    notification_type='assigned',
                    title=f'New Complaint Assigned: {complaint.title}',
                    message=f'A new {complaint.category} complaint has been assigned to you',
                    complaint_id=complaint.id
                )

def notify_on_status_change(complaint, old_status, new_status):
    """Notify user when complaint status changes (In-App notification + Email notification for ALL user roles)."""
    if complaint.user_id:
        if new_status == 'Resolved':
            message = f"Your complaint '{complaint.title}' has been resolved and archived."
        else:
            status_messages = {
                'Pending': 'Your complaint is pending review',
                'In Progress': 'Your complaint is being worked on'
            }
            message = status_messages.get(new_status, f'Status changed to {new_status}')

        # 1. In-App Notification
        create_notification(
            recipient_id=complaint.user_id,
            notification_type='status_changed',
            title=f'Complaint Status Updated: {new_status}',
            message=message,
            complaint_id=complaint.id
        )

        # 2. Universal Email Notification (Applies to ALL user roles: student, staff, worker, admin, principal)
        submitter = User.query.get(complaint.user_id)
        if submitter and getattr(submitter, 'email', None) and not submitter.email.endswith('@pending.college.edu'):
            try:
                from app import mail
                from flask import current_app, render_template, url_for
                from flask_mail import Message
                from datetime import datetime

                update_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                view_url = url_for('auth.login', _external=True) if has_request_context() else '/login'

                if has_request_context():
                    html_body = render_template(
                        'email_complaint_update.html',
                        complaint=complaint,
                        user=submitter,
                        time=update_time,
                        view_url=view_url
                    )
                else:
                    with current_app.test_request_context('/'):
                        html_body = render_template(
                            'email_complaint_update.html',
                            complaint=complaint,
                            user=submitter,
                            time=update_time,
                            view_url=view_url
                        )

                sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME') or 'noreply@campusvoice.edu'

                msg = Message(
                    subject=f"Complaint Status Updated ({new_status}): {complaint.title}",
                    sender=sender,
                    recipients=[submitter.email],
                    body=f"Hello {submitter.username},\n\nYour complaint '{complaint.title}' status has been updated to {new_status}.\n\nRemarks: {complaint.remarks or 'No remarks added'}\n\nView details: {view_url}",
                    html=html_body
                )

                mail_user = current_app.config.get('MAIL_USERNAME')
                mail_pass = current_app.config.get('MAIL_PASSWORD')
                if mail_user and mail_pass:
                    mail.send(msg)
                    logger.info(f"Dispatched status update email for Complaint ID {complaint.id} to {submitter.email}")
                    print(f"SUCCESS: Status update email sent for Complaint ID {complaint.id} to {submitter.email}")
                else:
                    logger.info(f"Status update email generated for Complaint ID {complaint.id} [SMTP credentials not set]")
            except Exception as e:
                logger.error(f"Failed to send complaint status update email to {submitter.email}: {e}")
                print(f"FAILED: Status update email crashed: {e}")

def notify_on_upvote(complaint, upvoter_id):
    """Notify user when their complaint is upvoted"""
    if complaint.user_id and complaint.user_id != upvoter_id:
        upvoter = User.query.get(upvoter_id)
        if upvoter and not complaint.is_confidential:
            create_notification(
                recipient_id=complaint.user_id,
                notification_type='upvoted',
                title='Your Complaint Received an Upvote!',
                message=f'{upvoter.username} upvoted your complaint. Current upvotes: {complaint.upvote_count}',
                complaint_id=complaint.id
            )

# ========== UPVOTE HELPERS ==========
def is_duplicate_upvote(complaint_id, user_id):
    """Check if user has already upvoted this complaint"""
    existing_upvote = Upvote.query.filter_by(
        complaint_id=complaint_id,
        user_id=user_id
    ).first()
    return existing_upvote is not None

def add_upvote(complaint_id, user_id):
    """Add an upvote to complaint if not duplicate"""
    if is_duplicate_upvote(complaint_id, user_id):
        return False, "You have already upvoted this complaint"

    complaint = Complaint.query.get(complaint_id)
    if not complaint:
        return False, "Complaint not found"

    if complaint.is_confidential:
        return False, "Cannot upvote confidential complaints"

    # Create upvote
    upvote = Upvote(complaint_id=complaint_id, user_id=user_id)
    db.session.add(upvote)

    # Update complaint upvote count and priority
    complaint.upvote_count += 1
    complaint.update_upvote_priority()

    db.session.commit()

    # Notify complaint creator
    notify_on_upvote(complaint, user_id)

    return True, "Upvote added successfully"

def remove_upvote(complaint_id, user_id):
    """Remove upvote from complaint"""
    upvote = Upvote.query.filter_by(
        complaint_id=complaint_id,
        user_id=user_id
    ).first()

    if not upvote:
        return False, "Upvote not found"

    complaint = Complaint.query.get(complaint_id)
    if complaint:
        complaint.upvote_count = max(0, complaint.upvote_count - 1)
        complaint.update_upvote_priority()

    db.session.delete(upvote)
    db.session.commit()

    return True, "Upvote removed"

def get_upvoters_list(complaint_id):
    """Get list of users who upvoted this complaint"""
    upvotes = Upvote.query.filter_by(complaint_id=complaint_id).all()
    return [upvote.to_dict() for upvote in upvotes]

# ========== VALIDATION HELPERS ==========
from utils.validators import validate_complaint_data as val_complaint, validate_status_update as val_status

def validate_complaint_data(data):
    """Validate complaint submission data using validators module."""
    return val_complaint(data)

def validate_status_update(new_status):
    """Validate status update using validators module."""
    return val_status(new_status)

# ========== AUDIT LOG HELPERS ==========
def log_audit(user_id, action, complaint_id=None, details=None):
    """Log an action for audit purposes"""
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        complaint_id=complaint_id,
        details=details
    )
    db.session.add(audit_log)
    db.session.commit()
    return audit_log

# ========== COMPLAINT HELPERS ==========
def get_complaints_for_user(user_id, role, department=None):
    """Get complaints based on user role"""
    if role == 'student':
        return Complaint.query.filter_by(user_id=user_id, is_confidential=False).all()

    elif role == 'worker':
        # Workers can see complaints for their department
        return Complaint.query.filter_by(
            category=department,
            is_confidential=False
        ).all()

    elif role == 'admin':
        # Admins can see complaints for their department
        return Complaint.query.filter_by(
            category=department,
            is_confidential=False
        ).all()

    elif role == 'principal':
        # Principal can see all complaints
        return Complaint.query.all()

    return []

def get_confidential_complaints():
    """Get all confidential complaints (for Principal only)"""
    return Complaint.query.filter_by(is_confidential=True).all()

# ========== NOTIFICATION HELPERS ==========
def mark_notification_as_read(notification_id, user_id):
    """Mark a notification as read"""
    notification = Notification.query.filter_by(
        id=notification_id,
        recipient_id=user_id
    ).first()

    if not notification:
        return False, "Notification not found"

    notification.is_read = True
    db.session.commit()
    return True, "Notification marked as read"

def get_user_notifications(user_id, limit=20, offset=0):
    """Get user notifications with pagination"""
    notifications = Notification.query.filter_by(
        recipient_id=user_id
    ).order_by(
        Notification.created_at.desc()
    ).limit(limit).offset(offset).all()

    return [notif.to_dict() for notif in notifications]

def get_unread_count(user_id):
    """Get count of unread notifications"""
    return Notification.query.filter_by(
        recipient_id=user_id,
        is_read=False
    ).count()

# ========== DUPLICATE DETECTION HELPERS ==========
from difflib import SequenceMatcher
import re

def extract_keywords(text):
    """Extract keywords from text by removing common words and lowercasing"""
    # Remove common English words
    common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'been', 'be', 'have', 'has', 
                   'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may',
                   'might', 'can', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                   'of', 'with', 'by', 'from', 'as', 'is', 'it', 'this', 'that', 'these',
                   'those', 'my', 'your', 'his', 'her', 'its', 'our', 'their'}
    
    # Convert to lowercase and split into words
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Filter out common words and short words
    keywords = [w for w in words if w not in common_words and len(w) > 2]
    
    return set(keywords)

def calculate_similarity(text1, text2):
    """Calculate similarity between two texts using SequenceMatcher (0-1 scale)"""
    ratio = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    return ratio

def calculate_keyword_overlap(text1, text2):
    """Calculate keyword overlap between two texts (0-1 scale)"""
    keywords1 = extract_keywords(text1)
    keywords2 = extract_keywords(text2)
    
    if not keywords1 or not keywords2:
        return 0
    
    overlap = keywords1.intersection(keywords2)
    total = keywords1.union(keywords2)
    
    return len(overlap) / len(total) if total else 0

def find_similar_complaints(title, description, category, location, min_similarity=0.4, limit=5, exclude_id=None):
    """
    Find similar complaints based on title, description, category, and location.
    Returns list of (complaint, similarity_score) tuples sorted by similarity.
    
    min_similarity: threshold for similarity score (0-1)
    limit: maximum number of similar complaints to return
    exclude_id: optional complaint ID to exclude from search (e.g. during edits)
    """
    # Get all non-confidential complaints in same category and exact location (excluding resolved ones)
    query = Complaint.query.filter(
        Complaint.category == category,
        Complaint.location.ilike(location),
        Complaint.is_confidential == False,
        Complaint.is_deleted == False,
        Complaint.status != 'Resolved'
    )

    if exclude_id:
        query = query.filter(Complaint.id != exclude_id)

    similar_complaints = query.all()
    
    results = []
    
    for complaint in similar_complaints:
        # Calculate combined similarity score
        title_similarity = calculate_similarity(title, complaint.title)
        desc_similarity = calculate_similarity(description, complaint.description)
        keyword_overlap = calculate_keyword_overlap(description, complaint.description)
        
        # Weighted average: title (30%), description (40%), keywords (30%)
        combined_score = (
            title_similarity * 0.3 +
            desc_similarity * 0.4 +
            keyword_overlap * 0.3
        )
        
        if combined_score >= min_similarity:
            results.append((complaint, round(combined_score, 2)))
    
    # Sort by similarity score (descending) and limit results
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


# ========== OVERDUE COMPLAINTS TRACKING ==========
def flag_overdue_complaints():
    """
    Automated system to flag complaints pending for more than 7 days as Overdue.
    Sends urgency notifications to assigned Admin/HOD and commits updates.
    """
    from datetime import timedelta
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    pending_complaints = Complaint.query.filter(
        Complaint.status == 'Pending',
        Complaint.is_overdue == False,
        Complaint.created_at <= seven_days_ago
    ).all()

    if not pending_complaints:
        return 0

    flagged_count = 0
    for complaint in pending_complaints:
        complaint.is_overdue = True
        flagged_count += 1

        # Notify assigned admin or department HOD(s)
        recipients = set()
        if complaint.assigned_to:
            recipients.add(complaint.assigned_to)
        else:
            creator_dept = complaint.creator.department if complaint.creator else None
            target_dept = complaint.category if complaint.category in ['Electrical/Plumbing', 'Hostel'] else creator_dept
            if target_dept:
                dept_admins = User.query.filter_by(role='admin', department=target_dept, active=True).all()
                for admin in dept_admins:
                    recipients.add(admin.id)

        for recip_id in recipients:
            create_notification(
                recipient_id=recip_id,
                notification_type='overdue_warning',
                title=f"URGENT: Complaint '{complaint.title}' is now Overdue",
                message=f"Complaint '{complaint.title}' has been pending for over 7 days and has been flagged to the Principal.",
                complaint_id=complaint.id
            )

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        import logging
        logging.getLogger(__name__).error(f"Error flagging overdue complaints: {e}")

    return flagged_count

