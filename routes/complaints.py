"""
Complaint Routes Module
Handles complaint submissions, edits, viewing, upvotes, supporting comments,
and dashboards for students and workers. Supports versioned and unversioned APIs.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, g, flash
import logging
from database import db, Complaint, User, Upvote, SupportingComment
from utils.decorators import login_required, role_required
from utils.helpers import (
    route_complaint_to_admin, notify_department_on_complaint,
    validate_complaint_data, is_duplicate_upvote, add_upvote,
    get_upvoters_list, notify_on_status_change, log_audit,
    find_similar_complaints, remove_upvote, api_response
)
from config import get_config

logger = logging.getLogger(__name__)
complaints_bp = Blueprint('complaints', __name__)


def dispatch_new_complaint_email(complaint):
    """Send automated new complaint notification email to target Admin / HOD or Principal."""
    if not complaint:
        return False

    try:
        from app import mail
        from flask import current_app, render_template, url_for
        from flask_mail import Message
        from datetime import datetime

        # Determine target recipient admins
        recipients = []
        if complaint.is_confidential or complaint.category in ['Ragging', 'Drug Abuse']:
            principals = User.query.filter_by(role='principal', active=True).all()
            recipients = [p.email for p in principals if p.email and not p.email.endswith('@pending.college.edu')]
        else:
            if complaint.assigned_to:
                assigned_admin = User.query.get(complaint.assigned_to)
                if assigned_admin and assigned_admin.email and not assigned_admin.email.endswith('@pending.college.edu'):
                    recipients.append(assigned_admin.email)

            if not recipients:
                admin_user = User.query.filter(User.role.in_(['admin', 'principal'])).first()
                if admin_user and admin_user.email and not admin_user.email.endswith('@pending.college.edu'):
                    recipients.append(admin_user.email)

        if not recipients:
            logger.info(f"No valid admin email found to notify for complaint ID {complaint.id}")
            return False

        submitter = User.query.get(complaint.user_id)
        submitter_identifier = (submitter.full_name or submitter.username) if submitter else "Student / User"
        created_time = complaint.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if complaint.created_at else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        from flask import has_request_context
        view_url = url_for('auth.login', _external=True) if has_request_context() else '/login'

        if has_request_context():
            html_body = render_template(
                'email_new_complaint.html',
                complaint=complaint,
                submitter_name=submitter_identifier,
                created_time=created_time,
                view_url=view_url
            )
        else:
            with current_app.test_request_context('/'):
                html_body = render_template(
                    'email_new_complaint.html',
                    complaint=complaint,
                    submitter_name=submitter_identifier,
                    created_time=created_time,
                    view_url=view_url
                )

        sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME') or 'noreply@campusvoice.edu'

        msg = Message(
            subject=f"New {complaint.priority} Priority Complaint: {complaint.title}",
            sender=sender,
            recipients=recipients,
            body=f"New Complaint Submitted:\nTitle: {complaint.title}\nCategory: {complaint.category}\nPriority: {complaint.priority}\nSubmitted By: {submitter_identifier}\nTimestamp: {created_time}\n\nView details: {view_url}",
            html=html_body
        )

        mail_user = current_app.config.get('MAIL_USERNAME')
        mail_pass = current_app.config.get('MAIL_PASSWORD')
        if mail_user and mail_pass:
            mail.send(msg)
            logger.info(f"Dispatched new complaint email alert for Complaint ID {complaint.id} to {recipients}")
            print(f"SUCCESS: New complaint email alert sent for Complaint ID {complaint.id} to {recipients}")
        else:
            logger.info(f"New complaint email alert generated for Complaint ID {complaint.id} [SMTP credentials not set]")
        return True
    except Exception as e:
        logger.error(f"Failed to send complaint alert email: {e}")
        print(f"FAILED: Complaint alert email error: {e}")
        return False


# ========== STUDENT DASHBOARD ==========
@complaints_bp.route('/complaints/dashboard/student', methods=['GET'])
@login_required
@role_required('student', 'staff')
def student_dashboard():
    """Student complaint dashboard"""
    user = g.current_user

    # Get student's complaints (excluding resolved/soft-deleted ones)
    complaints = Complaint.query.filter_by(user_id=user.id, is_deleted=False).order_by(
        Complaint.created_at.desc()
    ).all()

    # Dashboard metrics
    stats = {
        'total': len(complaints),
        'pending': len([c for c in complaints if c.status == 'Pending']),
        'in_progress': len([c for c in complaints if c.status == 'In Progress']),
        'resolved': len([c for c in complaints if c.status == 'Resolved'])
    }

    active_complaints = [c for c in complaints if c.status != 'Resolved']
    resolved_complaints = [c for c in complaints if c.status == 'Resolved']

    return render_template(
        'student_dashboard.html',
        active_complaints=active_complaints,
        resolved_complaints=resolved_complaints,
        stats=stats,
        user=user
    )


# ========== WORKER DASHBOARD ==========
@complaints_bp.route('/complaints/dashboard/worker', methods=['GET'])
@login_required
@role_required('worker', 'maintenance_worker')
def worker_dashboard():
    """Worker complaint dashboard"""
    user = g.current_user

    # Workers see complaints for their department (excluding soft-deleted ones)
    complaints = Complaint.query.filter_by(
        category=user.department,
        is_confidential=False,
        is_deleted=False
    ).order_by(Complaint.created_at.desc()).all()

    # Dashboard metrics
    stats = {
        'total': len(complaints),
        'pending': len([c for c in complaints if c.status == 'Pending']),
        'in_progress': len([c for c in complaints if c.status == 'In Progress']),
        'resolved': len([c for c in complaints if c.status == 'Resolved'])
    }

    active_complaints = [c for c in complaints if c.status != 'Resolved']
    resolved_complaints = [c for c in complaints if c.status == 'Resolved']

    return render_template(
        'worker_dashboard.html',
        active_complaints=active_complaints,
        resolved_complaints=resolved_complaints,
        stats=stats,
        user=user
    )

    return render_template(
        'worker_dashboard.html',
        active_complaints=active_complaints,
        resolved_complaints=resolved_complaints,
        stats=stats,
        user=user
    )


# ========== SUBMIT COMPLAINT ==========
@complaints_bp.route('/complaints/submit', methods=['GET', 'POST'])
@login_required
@role_required('student', 'staff', 'admin')
def submit_complaint():
    """Submit a new complaint with duplicate warning logic."""
    user = g.current_user
    config = get_config()

    if request.method == 'GET':
        categories = list(config.CATEGORY_ROUTING.keys())
        return render_template('submit_complaint.html', categories=categories, user=user)

    # Process POST request
    data = request.form
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    category = data.get('category', '').strip()
    location = data.get('location', '').strip()
    is_anonymous = False
    is_confidential = request.form.get('is_confidential') == 'on'
    skip_duplicate_check = request.form.get('skip_duplicate_check') == 'true' or user.role == 'admin'

    # Strict input validation
    errors = validate_complaint_data({
        'title': title,
        'description': description,
        'category': category,
        'priority': 'Low',
        'location': location
    })

    if errors:
        categories = list(config.CATEGORY_ROUTING.keys())
        return render_template('submit_complaint.html', categories=categories, errors=errors), 400

    # Duplicate warning check
    if not skip_duplicate_check and category not in config.CONFIDENTIAL_CATEGORIES:
        similar_complaints = find_similar_complaints(title, description, category, location, min_similarity=0.4, limit=5)
        if similar_complaints:
            categories = list(config.CATEGORY_ROUTING.keys())
            return render_template(
                'submit_complaint.html',
                categories=categories,
                user=user,
                title=title,
                description=description,
                category=category,
                priority='Low',
                location=location,
                is_anonymous=is_anonymous,
                similar_complaints=similar_complaints,
                show_duplicate_warning=True
            ), 200

    try:
        # Create DB record
        complaint = Complaint(
            user_id=user.id,
            title=title,
            description=description,
            category=category,
            location=location,
            is_anonymous=is_anonymous,
            status='Pending'
        )

        # Enforce confidentiality & HOD complaint to principal rule
        if user.role == 'admin' or category in config.CONFIDENTIAL_CATEGORIES:
            complaint.is_confidential = True
        elif is_confidential:
            complaint.is_confidential = False

        db.session.add(complaint)
        db.session.flush()

        # Automatic category admin assignment (bypassed if confidential)
        route_complaint_to_admin(complaint)
        db.session.commit()

        if user.role == 'admin':
            from database import Notification
            principals = User.query.filter_by(role='principal').all()
            for p in principals:
                notif = Notification(
                    recipient_id=p.id,
                    complaint_id=complaint.id,
                    title="New HOD Complaint to Principal",
                    message=f"Department HOD/Admin {user.full_name or user.username} ({user.department}) submitted a complaint to you: '{title}'",
                    notification_type='new_complaint'
                )
                db.session.add(notif)
            db.session.commit()
            flash('Your complaint has been submitted directly to the Principal.', 'success')
        else:
            # Trigger department notification alerts
            notify_department_on_complaint(complaint)

        # Audit logger
        log_audit(
            user_id=user.id,
            action='admin_submitted_complaint_to_principal' if user.role == 'admin' else 'submitted_complaint',
            complaint_id=complaint.id,
            details=f'Complaint title: {title} | Category: {category} | Location: {location}'
        )

        # Trigger automated email notification to target Admin/HOD or Principal
        try:
            dispatch_new_complaint_email(complaint)
        except Exception as mail_err:
            logger.error(f"Failed to dispatch new complaint email notification: {mail_err}")

        logger.info(f"New complaint submitted: ID {complaint.id} by User {user.username}")
        return redirect(url_for('complaints.view_complaint', complaint_id=complaint.id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to submit complaint: {e}", exc_info=True)
        categories = list(config.CATEGORY_ROUTING.keys())
        return render_template(
            'submit_complaint.html',
            categories=categories,
            errors=[f'Error submitting complaint: {str(e)}']
        ), 500


# ========== EDIT COMPLAINT ==========
@complaints_bp.route('/complaints/<int:complaint_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_complaint(complaint_id):
    """Edit an existing complaint."""
    complaint = Complaint.query.get_or_404(complaint_id)
    user = g.current_user
    config = get_config()

    # Permission check: Creator or designated department admin
    is_owner = complaint.user_id == user.id
    is_admin = user.role == 'admin' and complaint.category == user.department
    is_principal = user.is_principal()

    if not (is_owner or is_admin or is_principal):
        logger.warning(f"Unauthorized edit attempt on complaint {complaint_id} by {user.username}")
        from flask import abort
        abort(403)

    if request.method == 'GET':
        categories = list(config.CATEGORY_ROUTING.keys())
        return render_template('edit_complaint.html', complaint=complaint, categories=categories)

    # Process POST update
    data = request.form
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    category = data.get('category', '').strip()
    priority = data.get('priority', 'Low').strip()
    location = data.get('location', '').strip()
    skip_duplicate_check = request.form.get('skip_duplicate_check') == 'true'

    errors = validate_complaint_data({
        'title': title,
        'description': description,
        'category': category,
        'priority': priority,
        'location': location
    })

    if errors:
        categories = list(config.CATEGORY_ROUTING.keys())
        return render_template('edit_complaint.html', complaint=complaint, categories=categories, errors=errors, title=title, description=description, category=category, priority=priority, location=location), 400

    # Duplicate warning check for edits
    if not skip_duplicate_check and category not in config.CONFIDENTIAL_CATEGORIES:
        similar_complaints = find_similar_complaints(
            title, description, category, location, min_similarity=0.4, limit=5, exclude_id=complaint_id
        )
        if similar_complaints:
            categories = list(config.CATEGORY_ROUTING.keys())
            return render_template(
                'edit_complaint.html',
                complaint=complaint,
                categories=categories,
                user=user,
                title=title,
                description=description,
                category=category,
                priority=priority,
                location=location,
                similar_complaints=similar_complaints,
                show_duplicate_warning=True
            ), 200

    try:
        complaint.title = title
        complaint.description = description
        complaint.category = category
        complaint.priority = priority
        complaint.location = location

        db.session.commit()

        log_audit(
            user_id=user.id,
            action='edited_complaint',
            complaint_id=complaint.id,
            details=f'Complaint updated: {title} | Location: {location}'
        )

        logger.info(f"Complaint ID {complaint.id} successfully updated by {user.username}")
        return redirect(url_for('complaints.view_complaint', complaint_id=complaint.id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error editing complaint ID {complaint.id}: {e}", exc_info=True)
        categories = list(config.CATEGORY_ROUTING.keys())
        return render_template('edit_complaint.html', complaint=complaint, categories=categories, errors=[str(e)]), 500


# ========== VIEW COMPLAINT ==========
@complaints_bp.route('/complaints/<int:complaint_id>', methods=['GET'])
@login_required
def view_complaint(complaint_id):
    """View details of a single complaint."""
    complaint = Complaint.query.get_or_404(complaint_id)
    user = g.current_user

    # Permission evaluation
    is_owner = complaint.user_id == user.id
    is_admin = user.is_admin()
    is_assigned_admin = user.id == complaint.assigned_to
    is_principal = user.is_principal()

    can_view_public = not complaint.is_confidential
    can_view_confidential = is_principal and complaint.is_confidential

    if not (is_owner or can_view_public or can_view_confidential):
        from flask import abort
        abort(403)

    is_worker = user.role in ['worker', 'maintenance_worker']

    # Block non-staff/admin/worker users if complaint is soft-deleted / archived
    if complaint.is_deleted and not (is_principal or is_admin or is_worker):
        return render_template('error.html', error='This complaint has been resolved and archived.'), 403

    # Principals navigate standard complaints from records, not detailed inbox view
    if is_principal and not complaint.is_confidential:
        from flask import abort
        abort(403)

    if is_principal and complaint.is_confidential:
        return redirect(url_for('principal.view_confidential_complaint', complaint_id=complaint_id))

    # Retrieve state parameters
    has_upvoted = False
    if user.id != complaint.user_id and not complaint.is_confidential:
        has_upvoted = is_duplicate_upvote(complaint_id, user.id)

    upvoters = []
    if not complaint.is_confidential:
        upvoters = get_upvoters_list(complaint_id)

    can_edit_complaint = False
    if user.role == 'admin' and complaint.category == user.department and not complaint.is_confidential:
        can_edit_complaint = True

    role_dashboards = {
        'admin': 'admin.dashboard',
        'principal': 'principal.dashboard',
        'worker': 'complaints.worker_dashboard',
        'student': 'complaints.student_dashboard',
        'staff': 'complaints.student_dashboard'
    }
    dashboard_endpoint = role_dashboards.get(user.role, 'complaints.student_dashboard')

    return render_template('view_complaint.html',
                           complaint=complaint,
                           upvoters=upvoters,
                           has_upvoted=has_upvoted,
                           is_owner=is_owner,
                           is_admin=is_admin,
                           is_assigned_admin=is_assigned_admin,
                           can_edit_complaint=can_edit_complaint,
                           is_principal=is_principal,
                           dashboard_endpoint=dashboard_endpoint)


# ========== DELETE COMPLAINT ==========
@complaints_bp.route('/complaints/<int:complaint_id>/delete', methods=['POST'])
@login_required
def delete_complaint(complaint_id):
    """Delete a complaint (restricted to owner, admin or principal)."""
    complaint = Complaint.query.get_or_404(complaint_id)
    user = g.current_user

    if complaint.user_id != user.id and not user.is_admin():
        from flask import abort
        abort(403)

    try:
        db.session.delete(complaint)
        db.session.commit()

        log_audit(
            user_id=user.id,
            action='deleted_complaint',
            details=f'Deleted complaint ID {complaint_id}'
        )

        logger.info(f"Complaint ID {complaint_id} deleted by {user.username}")
        
        role_dashboards = {
            'admin': 'admin.dashboard',
            'principal': 'principal.dashboard',
            'worker': 'complaints.worker_dashboard',
            'student': 'complaints.student_dashboard'
        }
        return redirect(url_for(role_dashboards.get(user.role, 'home')))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting complaint ID {complaint_id}: {e}", exc_info=True)
        return render_template('error.html', error='Failed to delete complaint'), 500


# ========== API: UPVOTE COMPLAINT ==========
@complaints_bp.route('/api/v1/complaints/<int:complaint_id>/upvote', methods=['POST'])
@complaints_bp.route('/api/complaints/<int:complaint_id>/upvote', methods=['POST'])
@complaints_bp.route('/upvote/<int:complaint_id>', methods=['POST', 'GET'])
@login_required
def upvote_complaint(complaint_id):
    """Upvote a complaint."""
    user = g.current_user
    if user.role not in ['student', 'staff']:
        if request.is_json or request.path.startswith('/api/'):
            return api_response(False, message='You are not authorized to upvote complaints.', status_code=403)
        from flask import flash, redirect, url_for
        flash('You are not authorized to upvote complaints.', 'danger')
        role_dashboards = {
            'admin': 'admin.dashboard',
            'principal': 'principal.dashboard',
            'worker': 'complaints.worker_dashboard',
            'maintenance_worker': 'complaints.worker_dashboard'
        }
        dashboard_endpoint = role_dashboards.get(user.role, 'complaints.student_dashboard')
        return redirect(url_for(dashboard_endpoint))

    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.user_id == user.id:
        return api_response(False, message='Cannot upvote your own complaint', status_code=400)
    if complaint.is_confidential:
        return api_response(False, message='Cannot upvote confidential complaints', status_code=400)

    success, message = add_upvote(complaint_id, user.id)

    if success:
        return api_response(True, data={'upvote_count': complaint.upvote_count}, message=message)
    return api_response(False, message=message, status_code=400)


# ========== API: REMOVE UPVOTE ==========
@complaints_bp.route('/api/v1/complaints/<int:complaint_id>/upvote/remove', methods=['POST'])
@complaints_bp.route('/api/complaints/<int:complaint_id>/upvote/remove', methods=['POST'])
@login_required
def remove_upvote_complaint(complaint_id):
    """Remove upvote from complaint."""
    complaint = Complaint.query.get_or_404(complaint_id)
    user = g.current_user

    success, message = remove_upvote(complaint_id, user.id)

    if success:
        return api_response(True, data={'upvote_count': complaint.upvote_count}, message=message)
    return api_response(False, message=message, status_code=400)


# ========== API: GET UPVOTERS ==========
@complaints_bp.route('/api/v1/complaints/<int:complaint_id>/upvoters', methods=['GET'])
@complaints_bp.route('/api/complaints/<int:complaint_id>/upvoters', methods=['GET'])
@login_required
def get_upvoters(complaint_id):
    """Get list of users who upvoted a complaint."""
    complaint = Complaint.query.get_or_404(complaint_id)
    
    if complaint.is_confidential:
        return api_response(False, message='Confidential complaints do not have upvoters', status_code=403)

    upvoters = get_upvoters_list(complaint_id)
    return api_response(True, data={'upvoters': upvoters})


# ========== API: GET COMMENTS ==========
@complaints_bp.route('/api/v1/complaints/<int:complaint_id>/comments', methods=['GET'])
@complaints_bp.route('/api/complaints/<int:complaint_id>/comments', methods=['GET'])
@login_required
def get_comments(complaint_id):
    """Get list of supporting comments on a complaint."""
    complaint = Complaint.query.get_or_404(complaint_id)
    
    if complaint.is_confidential:
        return api_response(False, message='Confidential complaints do not support comments', status_code=403)

    comments = SupportingComment.query.filter_by(complaint_id=complaint_id).order_by(
        SupportingComment.created_at.asc()
    ).all()

    response_data = {
        'count': len(comments),
        'comments': [c.to_dict() for c in comments]
    }
    return api_response(True, data=response_data)


# ========== API: ADD COMMENT ==========
@complaints_bp.route('/api/v1/complaints/<int:complaint_id>/comment', methods=['POST'])
@complaints_bp.route('/api/complaints/<int:complaint_id>/comment', methods=['POST'])
@login_required
def add_comment(complaint_id):
    """Add a supporting comment to a complaint."""
    complaint = Complaint.query.get_or_404(complaint_id)
    user = g.current_user

    if complaint.is_confidential:
        return api_response(False, message='Cannot add comments to confidential complaints', status_code=403)

    data = request.get_json() or {}
    comment_text = data.get('comment', '').strip()
    is_anonymous = data.get('is_anonymous', False)

    if user.role in ['maintenance_worker', 'worker', 'admin', 'principal']:
        is_anonymous = False

    if not comment_text:
        return api_response(False, message='Comment cannot be empty', status_code=400)
    if len(comment_text) > 1000:
        return api_response(False, message='Comment too long (max 1000 characters)', status_code=400)

    try:
        new_comment = SupportingComment(
            complaint_id=complaint_id,
            user_id=user.id,
            comment=comment_text,
            is_anonymous=is_anonymous
        )

        db.session.add(new_comment)
        db.session.commit()

        logger.info(f"User {user.username} commented on Complaint ID {complaint_id}")
        return api_response(True, data=new_comment.to_dict(), message='Comment added successfully')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error posting comment on ID {complaint_id}: {e}", exc_info=True)
        return api_response(False, message=f'Error saving comment: {str(e)}', status_code=500)


# ========== API: FIND SIMILAR COMPLAINTS ==========
@complaints_bp.route('/api/v1/complaints/similar', methods=['POST'])
@complaints_bp.route('/api/complaints/similar', methods=['POST'])
@login_required
def check_similar_complaints():
    """API endpoint to find similar complaints dynamically by title, description, category, and location."""
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    category = data.get('category', '').strip()
    location = data.get('location', '').strip()
    min_similarity = float(data.get('min_similarity', 0.4))

    similar = find_similar_complaints(title, description, category, location, min_similarity=min_similarity)
    similar_list = [
        {
            'id': c.id,
            'title': c.title,
            'description': c.description,
            'category': c.category,
            'location': c.location,
            'status': c.status,
            'upvote_count': c.upvote_count,
            'similarity_score': score
        }
        for c, score in similar
    ]
    return api_response(True, data={'similar_complaints': similar_list, 'count': len(similar_list)})


# ========== API: SEARCH COMPLAINTS (DUAL FILTER LOCATION + KEYWORD) ==========
@complaints_bp.route('/api/v1/search_complaints', methods=['GET'])
@complaints_bp.route('/api/search_complaints', methods=['GET'])
@login_required
def api_search_complaints():
    """
    Search pending complaints strictly requiring BOTH location match and keyword match in title.
    Used by the Smart Suggestion Interceptor on complaint submission.
    """
    q = request.args.get('q', '').strip()
    location = request.args.get('location', '').strip()

    if not q or len(q) < 3 or not location:
        return jsonify([])

    matching_complaints = Complaint.query.filter(
        Complaint.location == location,
        Complaint.title.ilike(f'%{q}%'),
        Complaint.status == 'Pending',
        Complaint.is_deleted == False
    ).all()

    results = [c.to_dict() for c in matching_complaints]
    return jsonify(results)


# ========== UPDATE STATUS ROUTE ==========
@complaints_bp.route('/complaints/<int:complaint_id>/update_status', methods=['POST'])
@complaints_bp.route('/update_status/<int:complaint_id>', methods=['POST'])
@login_required
def update_status(complaint_id):
    """Update complaint status (Admins and Maintenance Workers)."""
    from flask import abort, flash
    from datetime import datetime

    user = g.current_user
    if not user or user.role not in ['admin', 'worker', 'maintenance_worker']:
        abort(403)

    complaint = Complaint.query.get_or_404(complaint_id)
    new_status = request.form.get('status', '').strip()

    config = get_config()
    if new_status not in config.VALID_STATUSES:
        flash('Invalid status selected.', 'error')
        return redirect(url_for('complaints.view_complaint', complaint_id=complaint_id))

    old_status = complaint.status
    complaint.status = new_status

    if new_status == 'Resolved':
        complaint.resolved_at = datetime.utcnow()
        complaint.is_deleted = True
    else:
        complaint.resolved_at = None
        complaint.is_deleted = False

    db.session.commit()

    notify_on_status_change(complaint, old_status, new_status)
    log_audit(
        user_id=user.id,
        action='resolved_complaint' if new_status == 'Resolved' else 'updated_status',
        complaint_id=complaint.id,
        details=f'Status updated: {old_status} -> {new_status}'
    )

    flash(f'Status successfully updated to {new_status}', 'success')
    return redirect(url_for('complaints.view_complaint', complaint_id=complaint_id))


