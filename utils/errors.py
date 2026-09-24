"""
Custom Exceptions and Global Error Handling
Provides unified API exception handler response structure and HTML view error routing.
"""

from flask import jsonify, render_template, request, current_app
import logging

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application exception."""
    status_code = 500
    message = "An unexpected error occurred"

    def __init__(self, message=None, status_code=None, payload=None):
        super().__init__()
        if message:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['success'] = False
        rv['message'] = self.message
        return rv


class ValidationError(AppError):
    """Raised when request data validation fails."""
    status_code = 400
    message = "Validation error"

    def __init__(self, message=None, errors=None):
        payload = {'errors': errors} if errors else None
        super().__init__(message, status_code=400, payload=payload)


class AuthenticationError(AppError):
    """Raised when authentication credentials are invalid or missing."""
    status_code = 401
    message = "Invalid username, password, or role choice."


class AuthorizationError(AppError):
    """Raised when a user is not permitted to perform an action."""
    status_code = 403
    message = "Access denied"


class NotFoundError(AppError):
    """Raised when a resource is not found."""
    status_code = 404
    message = "Resource not found"


def register_error_handlers(app):
    """Register custom exception error handlers for standard and API requests."""

    @app.errorhandler(AppError)
    def handle_app_error(error):
        logger.warning(f"AppError [{error.status_code}]: {error.message}")
        if request.path.startswith('/api/') or request.is_json:
            response = jsonify(error.to_dict())
            response.status_code = error.status_code
            return response
        return render_template('error.html', error=error.message), error.status_code

    @app.errorhandler(400)
    def bad_request(e):
        logger.error(f"400 Bad Request: {e}")
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'success': False, 'message': 'Bad Request'}), 400
        return render_template('error.html', error='Bad Request'), 400

    @app.errorhandler(403)
    def forbidden(e):
        logger.error(f"403 Forbidden: {e}")
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'success': False, 'message': 'Access Denied'}), 403
        return render_template('error.html', error='Access Denied'), 403

    @app.errorhandler(404)
    def not_found(e):
        logger.error(f"404 Not Found: {e}")
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
        return render_template('error.html', error='Page not found'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"500 Internal Server Error: {e}", exc_info=True)
        # Rollback db session just in case of uncommitted transaction
        from database import db
        try:
            db.session.rollback()
        except Exception:
            pass

        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'success': False, 'message': 'Internal Server Error'}), 500
        return render_template('error.html', error='Internal Server Error'), 500
