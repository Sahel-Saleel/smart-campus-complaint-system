"""
Principal Routes Module
Handles confidential complaint dashboards, audit logging HTML pages,
status updates, anonymity removal, and audit stats API endpoints.
Supports both versioned and unversioned routes and standard JSON response envelopes.
"""

from flask import Blueprint, render_template, request, url_for, session, jsonify, redirect, g
import logging
from database import db, Complaint, User, AuditLog
from utils.decorators import login_required, principal_required
from utils.helpers import notify_on_status_change, log_audit, api_response, cleanup_old_archives, flag_overdue_complaints

logger = logging.getLogger(__name__)
principal_bp = Blueprint('principal', __name__)


# ========== PRINCIPAL DASHBOARD (HTML records view) ==========
@principal_bp.route('/principal/dashboard', methods=['GET'])
@login_required
@principal_required
def dashboard():
    """Read-only archive log dashboard of all complaints for the principal."""
    cleanup_old_archives()
    flag_overdue_complaints()
    user = g.current_user
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    overdue_complaints = Complaint.query.filter_by(is_overdue=True).order_by(Complaint.created_at.desc()).all()

    # Log record viewing
    log_audit(
        user_id=user.id,
        action='accessed_principal_dashboard',
        details='Principal accessed read-only complaint records list'
    )

    return render_template('principal_records.html', complaints=complaints, overdue_complaints=overdue_complaints)


# ========== PRINCIPAL ACTIONABLE INBOX (HTML) ==========
@principal_bp.route('/principal/inbox', methods=['GET'])
@login_required
@principal_required
def inbox():
    """Actionable inbox of confidential complaints routed to the principal."""
    flag_overdue_complaints()
    user = g.current_user
    confidential_complaints = Complaint.query.filter_by(is_confidential=True).order_by(
        Complaint.created_at.desc()
    ).all()

    overdue_complaints = Complaint.query.filter_by(is_overdue=True).order_by(Complaint.created_at.desc()).all()

    # Metrics computation
    stats = {
        'total': len(confidential_complaints),
        'pending': len([c for c in confidential_complaints if c.status == 'Pending']),
        'in_progress': len([c for c in confidential_complaints if c.status == 'In Progress']),
        'resolved': len([c for c in confidential_complaints if c.status == 'Resolved']),
        'ragging': len([c for c in confidential_complaints if c.category == 'Ragging']),
        'drug_abuse': len([c for c in confidential_complaints if c.category == 'Drug Abuse'])
    }
    active_complaints = [c for c in confidential_complaints if c.status != 'Resolved']
    resolved_complaints = [c for c in confidential_complaints if c.status == 'Resolved']

    log_audit(
        user_id=user.id,
        action='accessed_confidential_dashboard',
        details='Principal accessed confidential complaints inbox'
    )

    return render_template('principal_dashboard.html',
                           active_complaints=active_complaints,
                           resolved_complaints=resolved_complaints,
                           overdue_complaints=overdue_complaints,
                           stats=stats,
                           user=user,
                           current_sort='date',
                           current_status='',
                           current_category='',
                           active_tab='complaints')


# ========== VIEW RECORD DETAIL (HTML View) ==========
@principal_bp.route('/principal/records/<int:complaint_id>', methods=['GET'])
@login_required
@principal_required
def view_record(complaint_id):
    """View details of a standard public complaint in read-only mode."""
    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.is_confidential:
        return redirect(url_for('principal.view_confidential_complaint', complaint_id=complaint_id))

    return render_template('principal_record_detail.html', complaint=complaint)


# ========== AUDIT LOG (HTML View) ==========
@principal_bp.route('/principal/audit-log', methods=['GET'])
@login_required
@principal_required
def audit_log():
    """View logged history of confidential complaint views and modifications."""
    user = g.current_user

    page = request.args.get('page', 1, type=int)
    limit = 50
    offset = (page - 1) * limit

    # Query matching audit actions
    actions_to_track = [
        'accessed_confidential_dashboard',
        'accessed_principal_dashboard',
        'viewed_confidential',
        'updated_status',
        'resolved_complaint',
        'added_remarks'
    ]

    total_logs = AuditLog.query.filter(AuditLog.action.in_(actions_to_track)).count()

    audit_logs = AuditLog.query.filter(
        AuditLog.action.in_(actions_to_track)
    ).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()

    total_pages = (total_logs + limit - 1) // limit

    return render_template('audit_log.html',
                           logs=audit_logs,
                           page=page,
                           total_pages=total_pages,
                           total_logs=total_logs)


# ========== VIEW CONFIDENTIAL COMPLAINT (HTML View) ==========
@principal_bp.route('/principal/complaints/<int:complaint_id>', methods=['GET'])
@login_required
@principal_required
def view_confidential_complaint(complaint_id):
    """View a single confidential complaint."""
    user = g.current_user
    complaint = Complaint.query.get_or_404(complaint_id)

    if not complaint.is_confidential:
        from flask import abort
        abort(403)

    log_audit(
        user_id=user.id,
        action='viewed_confidential',
        complaint_id=complaint_id,
        details=f'Viewed confidential complaint in category: {complaint.category}'
    )

    return render_template('view_confidential_complaint.html',
                           complaint=complaint,
                           is_principal=True)


# ========== UPDATE CONFIDENTIAL COMPLAINT STATUS (API) ==========
@principal_bp.route('/api/v1/confidential/<int:complaint_id>/status', methods=['PUT'])
@principal_bp.route('/api/confidential/<int:complaint_id>/status', methods=['PUT'])
@login_required
@principal_required
def update_confidential_status(complaint_id):
    """Update resolving status of confidential complaint."""
    user = g.current_user
    complaint = Complaint.query.get_or_404(complaint_id)

    if not complaint.is_confidential:
        return api_response(False, message='Not a confidential complaint', status_code=403)

    data = request.get_json() or {}
    new_status = data.get('status', '').strip()
    remarks = data.get('remarks', '').strip()

    valid_statuses = ['Pending', 'In Progress', 'Resolved']
    if new_status not in valid_statuses:
        return api_response(False, message='Invalid status value', status_code=400)

    try:
        old_status = complaint.status
        complaint.status = new_status
        if remarks:
            complaint.remarks = remarks

        db.session.commit()

        if complaint.user_id:
            notify_on_status_change(complaint, old_status, new_status)

        log_audit(
            user_id=user.id,
            action='updated_status',
            complaint_id=complaint_id,
            details=f'Confidential - {complaint.category} | Status: {old_status} -> {new_status}'
        )

        response_data = {
            'status': new_status,
            'updated_at': complaint.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        return api_response(True, data=response_data, message=f'Status updated to {new_status}')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating confidential status: {e}", exc_info=True)
        return api_response(False, message=str(e), status_code=500)


# ========== UPDATE CONFIDENTIAL COMPLAINT PRIORITY (API) ==========
@principal_bp.route('/api/v1/confidential/<int:complaint_id>/priority', methods=['PUT'])
@principal_bp.route('/api/confidential/<int:complaint_id>/priority', methods=['PUT'])
@login_required
@principal_required
def update_confidential_priority(complaint_id):
    """Update priority level of confidential complaint."""
    user = g.current_user
    complaint = Complaint.query.get_or_404(complaint_id)

    if not complaint.is_confidential:
        return api_response(False, message='Not a confidential complaint', status_code=403)

    data = request.get_json() or {}
    new_priority = data.get('priority', '').strip()

    valid_priorities = ['Low', 'Medium', 'High']
    if new_priority not in valid_priorities:
        return api_response(False, message='Invalid priority value', status_code=400)

    try:
        old_priority = complaint.priority
        complaint.priority = new_priority
        db.session.commit()

        log_audit(
            user_id=user.id,
            action='updated_priority',
            complaint_id=complaint_id,
            details=f'Confidential - {complaint.category} | Priority: {old_priority} -> {new_priority}'
        )

        response_data = {'priority': new_priority}
        return api_response(True, data=response_data, message=f'Priority updated to {new_priority}')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating confidential priority: {e}", exc_info=True)
        return api_response(False, message=str(e), status_code=500)


# ========== ADD REMARKS TO CONFIDENTIAL (API) ==========
@principal_bp.route('/api/v1/confidential/<int:complaint_id>/remarks', methods=['PUT'])
@principal_bp.route('/api/confidential/<int:complaint_id>/remarks', methods=['PUT'])
@login_required
@principal_required
def add_confidential_remarks(complaint_id):
    """Add administrator remarks to a confidential complaint."""
    user = g.current_user
    complaint = Complaint.query.get_or_404(complaint_id)

    if not complaint.is_confidential:
        return api_response(False, message='Not a confidential complaint', status_code=403)

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
            details=f'Confidential - {complaint.category} | Remarks added'
        )

        response_data = {'remarks': remarks}
        return api_response(True, data=response_data, message='Remarks added successfully')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding confidential remarks: {e}", exc_info=True)
        return api_response(False, message=str(e), status_code=500)


# ========== REMOVE ANONYMITY (API) ==========
@principal_bp.route('/api/v1/confidential/<int:complaint_id>/reveal-identity', methods=['POST'])
@principal_bp.route('/api/confidential/<int:complaint_id>/reveal-identity', methods=['POST'])
@login_required
@principal_required
def reveal_complaint_identity(complaint_id):
    """Reveal the name of the anonymous submitter (Principal Only)."""
    user = g.current_user
    complaint = Complaint.query.get_or_404(complaint_id)

    if not complaint.is_confidential:
        return api_response(False, message='Not a confidential complaint', status_code=403)
    if not complaint.is_anonymous:
        return api_response(False, message='Complaint is not anonymous', status_code=400)

    try:
        complaint.is_anonymous = False
        db.session.commit()

        log_audit(
            user_id=user.id,
            action='revealed_identity',
            complaint_id=complaint_id,
            details='Revealed identity of anonymous confidential complaint submitter'
        )

        creator_name = complaint.creator.username if complaint.creator else 'Unknown'
        response_data = {
            'creator_name': creator_name,
            'is_anonymous': False
        }
        return api_response(True, data=response_data, message='Identity revealed successfully')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error revealing identity for ID {complaint_id}: {e}", exc_info=True)
        return api_response(False, message=str(e), status_code=500)


# ========== SEARCH CONFIDENTIAL COMPLAINTS (API) ==========
@principal_bp.route('/api/v1/confidential/search', methods=['GET'])
@principal_bp.route('/api/confidential/search', methods=['GET'])
@login_required
@principal_required
def search_confidential():
    """Search confidential complaints by title or description."""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return api_response(False, message='Query must be at least 2 characters long', status_code=400)

    complaints = Complaint.query.filter(
        Complaint.is_confidential == True,
        (Complaint.title.ilike(f'%{query}%') | Complaint.description.ilike(f'%{query}%'))
    ).order_by(Complaint.created_at.desc()).limit(20).all()

    response_data = {
        'count': len(complaints),
        'complaints': [c.to_dict() for c in complaints]
    }
    return api_response(True, data=response_data)


# ========== GET AUDIT LOG STATS (API) ==========
@principal_bp.route('/api/v1/audit-stats', methods=['GET'])
@principal_bp.route('/api/audit-stats', methods=['GET'])
@login_required
@principal_required
def get_audit_stats():
    """Get stats aggregates from audit trail logs."""
    total_logs = AuditLog.query.count()
    confidential_access = AuditLog.query.filter_by(action='viewed_confidential').count()
    status_updates = AuditLog.query.filter_by(action='updated_status').count()

    last_log = AuditLog.query.order_by(AuditLog.created_at.desc()).first()
    last_access_time = last_log.created_at.strftime('%Y-%m-%d %H:%M:%S') if last_log else 'Never'

    response_data = {
        'total_logs': total_logs,
        'confidential_accesses': confidential_access,
        'status_updates': status_updates,
        'last_access': last_access_time
    }
    return api_response(True, data=response_data)
