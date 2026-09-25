"""
Complaint Management System - Flask Application
App Factory implementation with centralized configuration and Blueprint registry.
"""

import os
from datetime import timedelta
from flask import Flask, session, redirect, url_for, render_template
from flask_cors import CORS
from flask_migrate import Migrate
from flask_mail import Mail

from config import get_config
from database import db, User, Complaint, Notification, Upvote, AuditLog, CollegeStudent, PasswordResetRequest
from utils.logging_config import setup_logging
from utils.errors import register_error_handlers

# Initialize extensions
migrate = Migrate()
mail = Mail()


def create_app(config_class=None):
    """Application factory for creating and configuring the Flask app."""
    app = Flask(__name__)

    # Load configuration
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Setup logging configuration
    setup_logging(app)
    app.logger.info("Initializing app factory...")

    # Enable CORS
    CORS(app)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # Register error handlers
    register_error_handlers(app)

    # Context processor to inject user information on all templates
    @app.context_processor
    def inject_user():
        """Inject user info and notification count into all templates"""
        user = None
        unread_notifications_count = 0
        try:
            user_id = session.get('user_id')
            if user_id:
                user = User.query.get(user_id)
                if user:
                    unread_notifications_count = Notification.query.filter_by(
                        recipient_id=user_id,
                        is_read=False
                    ).count()
        except Exception:
            pass

        return dict(
            current_user=user,
            unread_notifications_count=unread_notifications_count
        )

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.complaints import complaints_bp
    from routes.admin import admin_bp
    from routes.principal import principal_bp
    from routes.notifications import notifications_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(principal_bp)
    app.register_blueprint(notifications_bp)

    # Force password change hook
    @app.before_request
    def force_change_password():
        """Force user to change default password on first login."""
        from flask import request
        if 'user_id' not in session:
            session.pop('change_password_required', None)
            return

        if session.get('change_password_required'):
            exempt_endpoints = [
                'auth.change_password',
                'auth.login',
                'auth.logout',
                'auth.forgot_password',
                'auth.verify_otp',
                'auth.verify_login_otp',
                'auth.resend_login_otp',
                'auth.register',
                'static'
            ]
            if request.endpoint:
                if request.endpoint in exempt_endpoints or request.endpoint.startswith('static'):
                    return
                return redirect(url_for('auth.change_password'))

    @app.after_request
    def prevent_caching_of_authenticated_pages(response):
        """Stop browsers caching logged-in pages, so pressing Back after logout
        cannot show a cached dashboard."""
        if 'user_id' in session and response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
        return response

    # Register one-time admin CLI commands (not run automatically)
    register_cli_commands(app)

    # Home redirection route
    @app.route('/')
    def home():
        """Home page - redirect to appropriate dashboard or login page"""
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))

        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('auth.login'))

        # Redirect based on role
        role_redirects = {
            'student': 'complaints.student_dashboard',
            'worker': 'complaints.worker_dashboard',
            'admin': 'admin.dashboard',
            'principal': 'principal.dashboard',
            'staff': 'complaints.student_dashboard'
        }

        redirect_route = role_redirects.get(user.role, 'auth.login')
        return redirect(url_for(redirect_route))

    return app


def init_db(app):
    """Ensure database tables exist.

    This runs on every start-up (see wsgi.py). It must NEVER create, recreate or
    modify user accounts or passwords - doing so previously reset management
    passwords and re-created demo accounts on every deploy/restart.
    Initial accounts are created only by the explicit one-time CLI command
    `flask --app wsgi bootstrap-accounts` (see register_cli_commands below).
    """
    from sqlalchemy import inspect, text
    with app.app_context():
        db.create_all()
        app.logger.info("Database tables verified/created.")

        # Ensure newly added columns exist on existing databases
        try:
            inspector = inspect(db.engine)
            if 'complaints' in inspector.get_table_names():
                columns = [c['name'] for c in inspector.get_columns('complaints')]
                if 'is_overdue' not in columns:
                    db.session.execute(text("ALTER TABLE complaints ADD COLUMN is_overdue BOOLEAN DEFAULT FALSE"))
                    db.session.commit()
                    app.logger.info("Migrated schema: Added 'is_overdue' column to 'complaints' table.")
                if 'is_anonymous' not in columns:
                    db.session.execute(text("ALTER TABLE complaints ADD COLUMN is_anonymous BOOLEAN DEFAULT FALSE"))
                    db.session.commit()
                    app.logger.info("Migrated schema: Added 'is_anonymous' column to 'complaints' table.")
        except Exception as migration_err:
            db.session.rollback()
            app.logger.error(f"Migration check error: {migration_err}")

        if User.query.count() == 0:
            app.logger.warning(
                "No user accounts exist. Run the one-time command "
                "'flask --app wsgi bootstrap-accounts' to create the management accounts."
            )


# Management accounts the institution needs (Principal, department admins and HODs).
# No passwords are stored here: bootstrap-accounts generates a random one-time
# password for each account it creates, and every account must complete
# first-login onboarding (set own password + email) before use.
MANAGEMENT_ACCOUNTS = [
    dict(username='principal', role='principal', department=None, full_name='Principal Office'),
    dict(username='NT069', role='admin', department='Electrical/Plumbing', full_name='Admin Electrical & Plumbing'),
    dict(username='TS182', role='admin', department='Computer Science and Engineering', full_name='HOD Computer Science and Engineering'),
    dict(username='TS176', role='admin', department='Mechanical Engineering', full_name='HOD Mechanical Engineering'),
    dict(username='TS057', role='admin', department='Artificial Intelligence and Data Science Engineering', full_name='HOD Artificial Intelligence and Data Science Engineering'),
    dict(username='TS400', role='admin', department='Electronics and Communication Engineering', full_name='HOD Electronics and Communication Engineering'),
    dict(username='TS442', role='admin', department='Electrical and Electronics Engineering', full_name='HOD Electrical and Electronics Engineering'),
    dict(username='TS387', role='admin', department='Civil Engineering', full_name='HOD Civil Engineering'),
    dict(username='TS468', role='admin', department='Applied Science and Humanities Engineering', full_name='HOD Applied Science and Humanities Engineering'),
]


def register_cli_commands(app):
    """One-time maintenance commands. These never run automatically."""
    import secrets
    import click
    from utils.security import hash_password, verify_password

    @app.cli.command('bootstrap-accounts')
    def bootstrap_accounts():
        """Create any MISSING management accounts with random one-time passwords.

        Existing accounts are never modified. Safe to run more than once.
        """
        created = []
        for spec in MANAGEMENT_ACCOUNTS:
            exists = User.query.filter(
                (db.func.lower(User.username) == spec['username'].lower()) |
                (db.func.lower(User.registration_number) == spec['username'].lower())
            ).first()
            if exists:
                continue
            temp_password = secrets.token_urlsafe(9)
            db.session.add(User(
                username=spec['username'],
                registration_number=spec['username'],
                role=spec['role'],
                department=spec['department'],
                full_name=spec['full_name'],
                email=f"{spec['username'].lower()}@pending.college.edu",
                password=hash_password(temp_password),
                active=True,
                password_changed_at=None,  # forces first-login onboarding
            ))
            created.append((spec['username'], temp_password))
        db.session.commit()

        if not created:
            click.echo("All management accounts already exist. Nothing was changed.")
            return
        click.echo("Created accounts (one-time passwords - shown only once, hand over securely):")
        for username, temp_password in created:
            click.echo(f"  {username:<10} {temp_password}")

    @app.cli.command('check-default-passwords')
    def check_default_passwords():
        """Read-only audit: list accounts whose password is still their username /
        registration number or an old published default. Changes nothing."""
        old_published_defaults = ['principal123', 'admin123', 'student123', 'worker123']
        flagged = []
        for u in User.query.order_by(User.role, User.username).all():
            candidates = {c for c in [u.username, (u.username or '').upper(), u.registration_number] if c}
            candidates.update(old_published_defaults)
            if any(verify_password(c, u.password) for c in candidates):
                flagged.append(u)
        if not flagged:
            click.echo("No accounts are using a default/published password.")
            return
        click.echo("Accounts still using a default/published password:")
        for u in flagged:
            state = 'not yet onboarded' if u.password_changed_at is None else 'onboarded'
            click.echo(f"  {u.username:<14} role={u.role:<10} dept={u.department or '-'}  ({state})")


if __name__ == '__main__':
    # When running directly, instantiate app and run
    app = create_app()
    init_db(app)

    # Run development server
    port = int(os.environ.get('PORT', 5000))
    debug = get_config().DEBUG
    app.run(host='0.0.0.0', port=port, debug=debug)
