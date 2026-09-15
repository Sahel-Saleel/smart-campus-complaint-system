from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, g, abort, flash
import logging
from database import db, Complaint, User, Notification, PasswordResetRequest
from utils.decorators import login_required, admin_required
from utils.helpers import (
    notify_on_status_change, log_audit, api_response, cleanup_old_archives,
    is_student_username, is_staff_username, extract_department_from_username,
    flag_overdue_complaints
)
from werkzeug.security import generate_password_hash
from utils.security import hash_password
from config import get_config

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def get_admin_complaints_query(user, include_resolved=False):
    """Build query for admin complaints based on department/branch scope."""
    query = Complaint.query.filter(Complaint.is_confidential == False)

    if not include_resolved:
        query = query.filter(Complaint.status != 'Resolved')
    else:
        query = query.filter(Complaint.status == 'Resolved')

    if user.is_principal():
        return query

    # Routing logic based on admin department
    if user.department == 'Electrical/Plumbing':
        query = query.filter(Complaint.category == 'Electrical/Plumbing')
    elif user.department == 'Hostel':
        query = query.filter(Complaint.category == 'Hostel')
    else:
        # Academic branch HOD admin (e.g. Computer Science Engineering, Mechanical Engineering)
        # Fetch complaints where category is 'Academic/General' AND creator's User.department matches admin's department
        query = query.join(User, Complaint.user_id == User.id).filter(
            Complaint.category == 'Academic/General',
            User.department == user.department
        )

    return query


# ========== ADMIN DASHBOARD (HTML Page) ==========
@admin_bp.route('/admin/dashboard', methods=['GET'])
@login_required
@admin_required
def dashboard():
    """Admin/Principal HTML dashboard"""
    cleanup_old_archives()
    flag_overdue_complaints()
    user = g.current_user

    # Retrieve all active complaints for this admin's department/scope
    complaints = get_admin_complaints_query(user, include_resolved=False).order_by(
        Complaint.created_at.desc()
    ).all()

    # Get aggregate stats
    stats = {
        'total': len(complaints),
        'pending': len([c for c in complaints if c.status == 'Pending']),
        'in_progress': len([c for c in complaints if c.status == 'In Progress']),
        'resolved': 0,
        'high_priority': len([c for c in complaints if c.priority == 'High']),
        'high_upvotes': len([c for c in complaints if c.upvote_count > 10])
    }

    # Parameters for sorting and filtering
    sort_by = request.args.get('sort', 'date')
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')

    if status_filter:
        complaints = [c for c in complaints if c.status == status_filter]

    if priority_filter:
        complaints = [c for c in complaints if c.priority == priority_filter]

    if sort_by == 'upvotes':
        complaints.sort(key=lambda x: x.upvote_count, reverse=True)
    elif sort_by == 'priority':
        priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
        complaints.sort(key=lambda x: priority_order.get(x.priority, 3))
    else:  # Date sorting
        complaints.sort(key=lambda x: x.created_at, reverse=True)

    active_complaints = complaints
    resolved_complaints = []

    # Retrieve pending student password reset requests
    reset_requests = PasswordResetRequest.query.filter_by(status='Pending').all()

    # Retrieve complaints submitted by this HOD/Admin directly to the Principal
    my_principal_complaints = Complaint.query.filter_by(user_id=user.id, is_confidential=True).order_by(Complaint.created_at.desc()).all()

    return render_template('admin_dashboard.html',
                           active_complaints=active_complaints,
                           resolved_complaints=resolved_complaints,
                           my_principal_complaints=my_principal_complaints,
                           stats=stats,
                           user=user,
                           current_sort=sort_by,
                           current_status=status_filter,
                           current_priority=priority_filter,
                           reset_requests=reset_requests)


# ========== ADMIN ARCHIVE PAGE ==========
@admin_bp.route('/admin/archive', methods=['GET'])
@login_required
@admin_required
def archive():
    """View resolved/archived complaints with restore/undo capabilities."""
    cleanup_old_archives()
    user = g.current_user

    archived_complaints = get_admin_complaints_query(user, include_resolved=True).order_by(
        Complaint.resolved_at.desc(),
        Complaint.created_at.desc()
    ).all()

    return render_template('admin_archive.html', complaints=archived_complaints, user=user)


# ========== UPDATE COMPLAINT STATUS (API) ==========
@admin_bp.route('/api/v1/complaints/<int:complaint_id>/status', methods=['PUT'])
@admin_bp.route('/api/complaints/<int:complaint_id>/status', methods=['PUT'])
@login_required
@admin_required
def update_complaint_status(complaint_id):
    """Update complaint status and remarks, supporting Archive/Undo."""
    complaint = Complaint.query.get_or_404(complaint_id)
    user = g.current_user

    # Auth logic
    if user.is_principal() and not complaint.is_confidential:
        return api_response(False, message='Regular complaints are read-only for the principal', status_code=403)
    if not user.is_principal():
        # Check authorization based on category & branch scope
        if complaint.category == 'Academic/General':
            if not (complaint.creator and complaint.creator.department == user.department):
                return api_response(False, message='Not authorized for this academic branch', status_code=403)
        elif complaint.category != user.department:
            return api_response(False, message='Not authorized for this department', status_code=403)

    data = request.get_json() or {}
    new_status = data.get('status', '').strip()
    remarks = data.get('remarks', '').strip()

    config = get_config()
    if new_status not in config.VALID_STATUSES:
        return api_response(False, message=f'Invalid status update. Choose from: {config.VALID_STATUSES}', status_code=400)

    try:
        old_status = complaint.status
        complaint.status = new_status
        if remarks:
            complaint.remarks = remarks

        if new_status == 'Resolved':
            complaint.resolved_at = datetime.utcnow()
            complaint.is_deleted = True
        else:
            # Undo / restore to Pending or In Progress
            complaint.resolved_at = None
            complaint.is_deleted = False

        db.session.commit()

        # Alert the user on status update
        notify_on_status_change(complaint, old_status, new_status)

        # Audit logs
        log_audit(
            user_id=user.id,
            action='resolved_complaint' if new_status == 'Resolved' else ('restored_complaint' if old_status == 'Resolved' else 'updated_status'),
            complaint_id=complaint_id,
            details=f'Status: {old_status} -> {new_status}. Resolved At: {complaint.resolved_at}. Remarks: {remarks[:50] if remarks else "None"}'
        )

        response_data = {
            'status': new_status,
            'updated_at': complaint.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        return api_response(True, data=response_data, message=f'Status updated to {new_status}')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating complaint status: {e}", exc_info=True)
        return api_response(False, message=f'Error updating status: {str(e)}', status_code=500)


# ========== UPDATE COMPLAINT PRIORITY (API) ==========
@admin_bp.route('/api/v1/complaints/<int:complaint_id>/priority', methods=['PUT'])
@admin_bp.route('/api/complaints/<int:complaint_id>/priority', methods=['PUT'])
@login_required
@admin_required
def update_complaint_priority(complaint_id):
    """Update complaint priority manually."""
    complaint = Complaint.query.get_or_404(complaint_id)
    user = g.current_user

    if user.is_principal() and not complaint.is_confidential:
        return api_response(False, message='Regular complaints are read-only for the principal', status_code=403)
    if not user.is_principal() and complaint.category != user.department:
         return api_response(False, message='Not authorized for this department', status_code=403)

    data = request.get_json() or {}
    new_priority = data.get('priority', '').strip()

    config = get_config()
    if new_priority not in config.VALID_PRIORITIES:
        return api_response(False, message=f'Invalid priority. Choose from: {config.VALID_PRIORITIES}', status_code=400)

    try:
        old_priority = complaint.priority
        complaint.priority = new_priority
        db.session.commit()

        log_audit(
            user_id=user.id,
            action='updated_priority',
            complaint_id=complaint_id,
            details=f'Priority: {old_priority} -> {new_priority}'
        )

        response_data = {'priority': new_priority}
        return api_response(True, data=response_data, message=f'Priority updated to {new_priority}')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating priority: {e}", exc_info=True)
        return api_response(False, message=f'Error updating priority: {str(e)}', status_code=500)


# ========== ADD REMARKS (API) ==========
@admin_bp.route('/api/v1/complaints/<int:complaint_id>/remarks', methods=['PUT'])
@admin_bp.route('/api/complaints/<int:complaint_id>/remarks', methods=['PUT'])
@login_required
@admin_required
def add_remarks(complaint_id):
    """Add administrator remarks to a complaint."""
    complaint = Complaint.query.get_or_404(complaint_id)
    user = g.current_user

    if user.is_principal() and not complaint.is_confidential:
         return api_response(False, message='Regular complaints are read-only for the principal', status_code=403)
    if not user.is_principal() and complaint.category != user.department:
         return api_response(False, message='Not authorized for this department', status_code=403)

    data = request.get_json() or {}
    remarks = data.get('remarks', '').strip()

    if not remarks:
        return api_response(False, message='Remarks cannot be empty', status_code=400)
    if len(remarks) > 2000:
        return api_response(False, message='Remarks too long (max 2000 characters)', status_code=400)

    try:
        complaint.remarks = remarks
        db.session.commit()

        log_audit(
            user_id=user.id,
            action='added_remarks',
            complaint_id=complaint_id,
            details=f'Remarks added: {remarks[:100]}...'
        )

        response_data = {'remarks': remarks}
        return api_response(True, data=response_data, message='Remarks added successfully')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding remarks: {e}", exc_info=True)
        return api_response(False, message=f'Error adding remarks: {str(e)}', status_code=500)


# ========== REASSIGN COMPLAINT (API) ==========
@admin_bp.route('/api/v1/complaints/<int:complaint_id>/assign', methods=['PUT'])
@admin_bp.route('/api/complaints/<int:complaint_id>/assign', methods=['PUT'])
@login_required
@admin_required
def reassign_complaint(complaint_id):
    """Reassign complaint to another administrator."""
    complaint = Complaint.query.get_or_404(complaint_id)
    user = g.current_user

    # Reassignment permission restricted to Principal
    if not user.is_principal():
        return api_response(False, message='Only the principal can reassign complaints', status_code=403)
    if not complaint.is_confidential:
        return api_response(False, message='Regular complaints cannot be reassigned by principal', status_code=403)

    data = request.get_json() or {}
    admin_id = data.get('admin_id')

    if not admin_id:
        return api_response(False, message='Admin ID is required', status_code=400)

    new_admin = User.query.get(admin_id)
    if not new_admin or new_admin.role != 'admin':
        return api_response(False, message='Invalid administrator selected', status_code=400)

    try:
        old_admin_id = complaint.assigned_to
        complaint.assigned_to = admin_id

        # Notify the assigned administrator
        new_notification = Notification(
            recipient_id=admin_id,
            complaint_id=complaint_id,
            notification_type='assigned',
            title=f'Complaint Assigned to You: {complaint.title}',
            message=f'Principal assigned you a new complaint under {complaint.category}',
            is_read=False
        )
        db.session.add(new_notification)
        db.session.commit()

        log_audit(
            user_id=user.id,
            action='reassigned_complaint',
            complaint_id=complaint_id,
            details=f'Reassigned from Admin {old_admin_id} to Admin {admin_id}'
        )

        response_data = {
            'assigned_to_id': admin_id,
            'assigned_to_name': new_admin.username
        }
        return api_response(True, data=response_data, message=f'Assigned to {new_admin.username}')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error reassigning complaint: {e}", exc_info=True)
        return api_response(False, message=f'Error reassigning: {str(e)}', status_code=500)


# ========== SEARCH COMPLAINTS (API) ==========
@admin_bp.route('/api/v1/complaints/search', methods=['GET'])
@admin_bp.route('/api/complaints/search', methods=['GET'])
@login_required
@admin_required
def search_complaints():
    """Search department/all complaints by title or description."""
    user = g.current_user
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return api_response(False, message='Search query must be at least 2 characters long', status_code=400)

    # Base complaints filter
    if user.is_principal():
        complaints = Complaint.query.filter_by(is_confidential=False).all()
    else:
        complaints = Complaint.query.filter_by(
            category=user.department,
            is_confidential=False
        ).all()

    # Search query filter
    results = [
        c for c in complaints
        if query.lower() in c.title.lower() or query.lower() in c.description.lower()
    ]

    response_data = {
        'count': len(results),
        'complaints': [c.to_dict() for c in results[:20]]
    }
    return api_response(True, data=response_data, message='Search search completed')


# ========== GET ALL ADMINS (API) ==========
@admin_bp.route('/api/v1/admins', methods=['GET'])
@admin_bp.route('/api/admins', methods=['GET'])
@login_required
@admin_required
def get_all_admins():
    """Retrieve lists of all active admins (restricted to principal)."""
    user = g.current_user

    if not user.is_principal():
        return api_response(False, message='Access restricted to principal', status_code=403)

    admins = User.query.filter_by(role='admin', active=True).all()
    response_data = {
        'admins': [{'id': a.id, 'username': a.username, 'department': a.department} for a in admins]
    }
    return api_response(True, data=response_data, message='Active admins retrieved')


# ========== APPROVE/REJECT PASSWORD RESET REQUESTS ==========
@admin_bp.route('/admin/reset-requests/<int:request_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_reset_request(request_id):
    """Approve a password reset request, reverting password to default (registration number or username)."""
    req = PasswordResetRequest.query.get_or_404(request_id)
    if req.status != 'Pending':
        return redirect(url_for('admin.dashboard'))

    target_user = req.user
    if target_user:
        # Reset password back to default (Registration Number or Username)
        default_pwd = target_user.registration_number or target_user.username
        target_user.password = hash_password(default_pwd)
        target_user.password_changed_at = None  # Force password change on next login
        req.status = 'Approved'
        db.session.commit()
        log_audit(target_user.id, 'PASSWORD_RESET_APPROVED_BY_ADMIN', details=f"Password reset to default for {target_user.username}")
        logger.info(f"Admin approved password reset for user: {target_user.username}")
        
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/reset-requests/<int:request_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_reset_request(request_id):
    """Reject a student password reset request."""
    req = PasswordResetRequest.query.get_or_404(request_id)
    if req.status != 'Pending':
        return redirect(url_for('admin.dashboard'))

    req.status = 'Rejected'
    db.session.commit()
    logger.info(f"Admin rejected password reset for request id: {request_id}")
    
    return redirect(url_for('admin.dashboard'))


# ========== MANAGE DEPARTMENT USERS (HOD ONLY) ==========
@admin_bp.route('/manage_users', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_users():
    """Manage department students and staff (Academic HOD only)."""
    current_user = g.current_user
    if not current_user or current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        raw_id = (request.form.get('new_username') or 
                  request.form.get('registration_number') or 
                  request.form.get('staff_id') or 
                  request.form.get('username') or '').strip()

        if not raw_id:
            flash('Username / Registration Number / Staff ID is required.', 'error')
            return redirect(url_for('admin.manage_users'))

        identifier = raw_id.upper().strip()

        existing_user = User.query.filter_by(username=identifier).first() or User.query.filter_by(registration_number=identifier).first()
        if existing_user:
            flash(f'User "{identifier}" already exists.', 'error')
            return redirect(url_for('admin.manage_users'))

        hashed_password = hash_password(identifier)

        is_maintenance_dept = current_user.department in ['Electrical/Plumbing', 'Facilities', 'Maintenance']
        submitted_role = request.form.get('role', '').strip().lower()

        # Server-side security validation to prevent form tampering
        if is_maintenance_dept:
            if submitted_role and submitted_role not in ['worker', 'maintenance_worker']:
                flash('Unauthorized: Maintenance admins can only add maintenance workers.', 'error')
                return redirect(url_for('admin.manage_users'))

            new_user = User(
                username=identifier,
                role='worker',
                department=current_user.department,
                registration_number=identifier,
                email=f"{identifier.lower()}@college.edu",
                password=hashed_password,
                active=True,
                is_first_login=True
            )
        else:
            if submitted_role in ['worker', 'maintenance_worker']:
                flash('Unauthorized: Academic HODs cannot add maintenance workers.', 'error')
                return redirect(url_for('admin.manage_users'))

            if submitted_role == 'student' or (not submitted_role and is_student_username(identifier)):
                if is_student_username(identifier):
                    extracted_dept = extract_department_from_username(identifier)
                    if extracted_dept != current_user.department:
                        flash('You can only add students to your own department.', 'error')
                        return redirect(url_for('admin.manage_users'))

                new_user = User(
                    username=identifier,
                    role='student',
                    department=current_user.department,
                    registration_number=identifier,
                    email=f"{identifier.lower()}@college.edu",
                    password=hashed_password,
                    active=True,
                    is_first_login=True
                )
            elif submitted_role in ['staff', 'faculty'] or (not submitted_role and is_staff_username(identifier)):
                new_user = User(
                    username=identifier,
                    role='staff',
                    department=current_user.department,
                    registration_number=identifier,
                    email=f"{identifier.lower()}@college.edu",
                    password=hashed_password,
                    active=True,
                    is_first_login=True
                )
            else:
                flash('Invalid user format or role selection.', 'error')
                return redirect(url_for('admin.manage_users'))

        db.session.add(new_user)
        db.session.commit()
        log_audit(current_user.id, 'ADD_USER', details=f"Added user {new_user.username} to {current_user.department}")
        flash(f'User {new_user.username} added successfully with default password.', 'success')
        return redirect(url_for('admin.manage_users'))

    # GET Request
    dept_users = User.query.filter(
        User.department == current_user.department,
        User.id != current_user.id
    ).all()

    students = [u for u in dept_users if u.role == 'student']
    staff = [u for u in dept_users if u.role in ('staff', 'faculty')]
    workers = [u for u in dept_users if u.role in ('worker', 'maintenance_worker')]

    return render_template('manage_users.html', students=students, staff=staff, workers=workers, user=current_user)


@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Remove a user from the admin's department."""
    current_user = g.current_user
    if not current_user or current_user.role != 'admin':
        abort(403)

    user = User.query.get_or_404(user_id)

    # Strict security check: User must belong to HOD's department and HOD cannot delete themselves
    if user.department != current_user.department or user.id == current_user.id:
        abort(403)

    db.session.delete(user)
    db.session.commit()
    log_audit(current_user.id, 'REMOVE_USER', details=f"Removed user {user.username} from {current_user.department}")
    flash('User removed successfully', 'success')
    return redirect(url_for('admin.manage_users'))


