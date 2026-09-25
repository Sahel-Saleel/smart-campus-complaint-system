"""
Access Control and Authentication Decorators
Provides caching of current_user in Flask global context 'g' and route protection.
"""

from flask import session, redirect, url_for, abort, request, jsonify, g
from functools import wraps
from database import User, Complaint, AuditLog, db
from config import get_config


def get_current_user():
    """Retrieve and cache the current logged-in user in Flask 'g' context."""
    if 'current_user' not in g:
        user_id = session.get('user_id')
        if user_id:
            g.current_user = User.query.get(user_id)
        else:
            g.current_user = None
    return g.current_user


def login_required(f):
    """Decorator to check if user is logged in, with caching."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or not user.active:
            session.clear()
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*required_roles):
    """Decorator to check if user has one of the required roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                if request.path.startswith('/api/') or request.is_json:
                    return jsonify({'success': False, 'message': 'Not authenticated'}), 401
                abort(401)

            if user.role not in required_roles:
                if request.path.startswith('/api/') or request.is_json:
                    return jsonify({'success': False, 'message': 'Access denied'}), 403
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Decorator to check if user is an admin or principal."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            abort(401)

        if not user.is_admin():
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': 'Admin access required'}), 403
            abort(403)

        return f(*args, **kwargs)
    return decorated_function


def principal_required(f):
    """Decorator to check if user is the principal."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            abort(401)

        if not user.is_principal():
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': 'Principal access required'}), 403
            abort(403)

        return f(*args, **kwargs)
    return decorated_function


def log_confidential_access(f):
    """Decorator to log audit accesses to confidential complaints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            abort(401)

        complaint_id = kwargs.get('complaint_id') or kwargs.get('id')
        if complaint_id:
            audit_log = AuditLog(
                user_id=user.id,
                action='viewed_confidential',
                complaint_id=complaint_id,
                details=f'{user.username} ({user.role}) accessed confidential complaint'
            )
            db.session.add(audit_log)
            db.session.commit()

        return f(*args, **kwargs)
    return decorated_function


def complaint_owner_required(f):
    """Decorator to check if user is the complaint creator or elevated user."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            abort(401)

        complaint_id = kwargs.get('complaint_id') or kwargs.get('id')
        if not complaint_id:
            abort(400)

        complaint = Complaint.query.get(complaint_id)
        if not complaint:
            abort(404)

        if complaint.user_id != user.id and not user.is_admin():
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': 'You can only access or modify your own complaints'}), 403
            abort(403)

        return f(*args, **kwargs)
    return decorated_function
