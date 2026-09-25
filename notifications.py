"""
Notification Routes Module
Handles user notifications viewing HTML page and JSON API management endpoints.
Supports both versioned and unversioned routes and standard JSON response envelopes.
"""

from flask import Blueprint, render_template, request, session, jsonify, g
import logging
from database import db, Notification, User
from utils.decorators import login_required
from utils.helpers import get_user_notifications, get_unread_count, mark_notification_as_read, api_response

logger = logging.getLogger(__name__)
notifications_bp = Blueprint('notifications', __name__)


# ========== NOTIFICATIONS PAGE (HTML View) ==========
@notifications_bp.route('/notifications', methods=['GET'])
@login_required
def notifications_page():
    """View all notifications in HTML dashboard layout."""
    user = g.current_user
    
    page = request.args.get('page', 1, type=int)
    limit = 20
    offset = (page - 1) * limit

    total = Notification.query.filter_by(recipient_id=user.id).count()
    total_pages = (total + limit - 1) // limit

    notifications = Notification.query.filter_by(
        recipient_id=user.id
    ).order_by(
        Notification.created_at.desc()
    ).limit(limit).offset(offset).all()

    return render_template('notifications.html',
                           notifications=notifications,
                           page=page,
                           total_pages=total_pages,
                           total_count=total,
                           user=user)


# ========== GET NOTIFICATIONS (API) ==========
@notifications_bp.route('/api/v1/notifications', methods=['GET'])
@notifications_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Get user notifications (JSON API)."""
    user = g.current_user
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)

    notifications = get_user_notifications(user.id, limit, (page - 1) * limit)
    unread_count = get_unread_count(user.id)

    response_data = {
        'notifications': notifications,
        'unread_count': unread_count,
        'page': page
    }
    return api_response(True, data=response_data)


# ========== GET UNREAD COUNT (API) ==========
@notifications_bp.route('/api/v1/notifications/unread-count', methods=['GET'])
@notifications_bp.route('/api/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notifications():
    """Get count of unread notifications."""
    user = g.current_user
    unread_count = get_unread_count(user.id)
    return api_response(True, data={'unread_count': unread_count})


# ========== MARK AS READ (API) ==========
@notifications_bp.route('/api/v1/notifications/<int:notification_id>/read', methods=['PUT'])
@notifications_bp.route('/api/notifications/<int:notification_id>/read', methods=['PUT'])
@login_required
def mark_as_read(notification_id):
    """Mark a specific notification as read."""
    user = g.current_user
    success, message = mark_notification_as_read(notification_id, user.id)

    if success:
        return api_response(True, message=message)
    return api_response(False, message=message, status_code=404)


# ========== MARK ALL AS READ (API) ==========
@notifications_bp.route('/api/v1/notifications/mark-all-read', methods=['POST'])
@notifications_bp.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_as_read():
    """Mark all notifications as read for current user."""
    user = g.current_user

    try:
        notifications = Notification.query.filter_by(
            recipient_id=user.id,
            is_read=False
        ).all()

        count = len(notifications)
        for notif in notifications:
            notif.is_read = True

        db.session.commit()
        logger.info(f"Marked {count} notifications as read for {user.username}")
        return api_response(True, data={'count': count}, message=f'Marked {count} notifications as read')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking all read for {user.username}: {e}", exc_info=True)
        return api_response(False, message=str(e), status_code=500)


# ========== DELETE NOTIFICATION (API) ==========
@notifications_bp.route('/api/v1/notifications/<int:notification_id>', methods=['DELETE'])
@notifications_bp.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """Delete a specific notification."""
    user = g.current_user

    notification = Notification.query.filter_by(
        id=notification_id,
        recipient_id=user.id
    ).first()

    if not notification:
        return api_response(False, message='Notification not found', status_code=404)

    try:
        db.session.delete(notification)
        db.session.commit()
        return api_response(True, message='Notification deleted')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting notification {notification_id}: {e}", exc_info=True)
        return api_response(False, message=str(e), status_code=500)


# ========== DELETE ALL NOTIFICATIONS (API) ==========
@notifications_bp.route('/api/v1/notifications/delete-all', methods=['DELETE', 'POST'])
@notifications_bp.route('/api/notifications/delete-all', methods=['DELETE', 'POST'])
@login_required
def delete_all_notifications():
    """Delete all notifications for current user."""
    user = g.current_user

    try:
        notifications = Notification.query.filter_by(recipient_id=user.id).all()
        count = len(notifications)

        for notif in notifications:
            db.session.delete(notif)

        db.session.commit()
        logger.info(f"Deleted {count} notifications for {user.username}")
        return api_response(True, data={'count': count}, message=f'Deleted {count} notifications')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting all notifications for {user.username}: {e}", exc_info=True)
        return api_response(False, message=str(e), status_code=500)


# ========== GET NOTIFICATION STATS (API) ==========
@notifications_bp.route('/api/v1/notifications/stats', methods=['GET'])
@notifications_bp.route('/api/notifications/stats', methods=['GET'])
@login_required
def get_notification_stats():
    """Get count metrics of notification types."""
    user = g.current_user

    total = Notification.query.filter_by(recipient_id=user.id).count()
    unread = get_unread_count(user.id)
    by_type = {}

    for notification_type in ['new_complaint', 'status_changed', 'assigned', 'upvoted']:
        count = Notification.query.filter_by(
            recipient_id=user.id,
            notification_type=notification_type
        ).count()
        if count > 0:
            by_type[notification_type] = count

    response_data = {
        'total': total,
        'unread': unread,
        'read': total - unread,
        'by_type': by_type
    }
    return api_response(True, data=response_data)


# ========== FILTER NOTIFICATIONS (API) ==========
@notifications_bp.route('/api/v1/notifications/filter', methods=['GET'])
@notifications_bp.route('/api/notifications/filter', methods=['GET'])
@login_required
def filter_notifications():
    """Filter list of notifications by type or read status."""
    user = g.current_user
    notification_type = request.args.get('type', '').strip()
    read_status = request.args.get('read', '').strip()

    query = Notification.query.filter_by(recipient_id=user.id)

    if notification_type:
        query = query.filter_by(notification_type=notification_type)

    if read_status == 'read':
        query = query.filter_by(is_read=True)
    elif read_status == 'unread':
        query = query.filter_by(is_read=False)

    notifications = query.order_by(Notification.created_at.desc()).limit(50).all()
    
    response_data = {
        'count': len(notifications),
        'notifications': [n.to_dict() for n in notifications]
    }
    return api_response(True, data=response_data)
