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
    """Initialize database tables and create sample data if empty."""
    from werkzeug.security import generate_password_hash
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
                    db.session.execute(text("ALTER TABLE complaints ADD COLUMN is_overdue BOOLEAN DEFAULT 0"))
                    db.session.commit()
                    app.logger.info("Migrated SQLite schema: Added 'is_overdue' column to 'complaints' table.")
                if 'is_anonymous' not in columns:
                    db.session.execute(text("ALTER TABLE complaints ADD COLUMN is_anonymous BOOLEAN DEFAULT 0"))
                    db.session.commit()
                    app.logger.info("Migrated SQLite schema: Added 'is_anonymous' column to 'complaints' table.")
        except Exception as migration_err:
            db.session.rollback()
            app.logger.error(f"Migration check error: {migration_err}")

        # Ensure college students are populated
        if CollegeStudent.query.count() == 0:
            populate_college_students()

        if User.query.count() == 0:
            create_sample_data()

        # Explicitly ensure TS182 exists as Admin (HOD) for Computer Science Engineering
        hod_cs = User.query.filter_by(username='TS182').first()
        if not hod_cs:
            hod_cs = User(
                username='TS182',
                registration_number='TS182',
                role='admin',
                department='Computer Science Engineering',
                full_name='HOD Computer Science Engineering',
                email='ts182@college.com',
                password=generate_password_hash('TS182'),
                active=True,
                password_changed_at=None
            )
            db.session.add(hod_cs)
            db.session.commit()
            app.logger.info("Explicitly created/verified TS182 CS HOD Admin account.")

        # Explicitly ensure Principal user exists ('principal' / 'principal123')
        principal_user = User.query.filter((db.func.lower(User.username) == 'principal') | (User.role == 'principal')).first()
        if not principal_user:
            principal_user = User(
                username='principal',
                registration_number='principal',
                role='principal',
                full_name='Principal Office',
                email='principal@pending.college.edu',
                password=generate_password_hash('principal123'),
                active=True,
                password_changed_at=None
            )
            db.session.add(principal_user)
            db.session.commit()
            app.logger.info("Explicitly created Principal account ('principal' / 'principal123').")
        else:
            if principal_user.username.lower() != 'principal':
                principal_user.username = 'principal'
                principal_user.registration_number = 'principal'
                if principal_user.password_changed_at is None:
                    principal_user.password = generate_password_hash('principal123')
                db.session.commit()

        sync_admin_default_passwords()


def sync_admin_default_passwords():
    """Ensure all Admin, HOD, and Principal accounts have initial password set to registration number/default password if not yet changed."""
    from werkzeug.security import generate_password_hash
    from utils.security import verify_password
    admin_users = User.query.filter(User.role.in_(['admin', 'principal'])).all()
    updated = False
    for u in admin_users:
        if u.password_changed_at is not None:
            continue
        default_pass = 'principal123' if (u.role == 'principal' or u.username.lower() == 'principal') else (u.registration_number or u.username)
        if not default_pass:
            continue
        if not verify_password(default_pass, u.password):
            u.password = generate_password_hash(default_pass)
            if u.role == 'principal' or u.username.lower() == 'principal':
                u.username = 'principal'
                u.registration_number = 'principal'
            else:
                u.registration_number = default_pass
            updated = True
    if updated:
        db.session.commit()


def populate_college_students():
    """Populate database of valid student registration numbers."""
    valid_numbers = [
        'SPT24CS001',
        'SPT24AD045',
        'SPT25EC112',
        'SPT23ME256',
        'SPT26EE003',
        'SPT24CE002',
        'SPT24CS003',
        'SPT24CS091',
        'SPT24CS092',
        'SPT24CS090',
        'SPT24CS096',
        'SPT24CS099'
    ]
    for reg in valid_numbers:
        student = CollegeStudent(registration_number=reg)
        db.session.add(student)
    db.session.commit()
    print("[OK] Pre-verified student database populated!")


def create_sample_data():
    """Create essential top-level principal, admin, and HOD accounts with default passwords for onboarding."""
    from werkzeug.security import generate_password_hash

    # Create top-level management users
    principal = User(
        username='principal',
        registration_number='principal',
        email='principal@pending.college.edu',
        password=generate_password_hash('principal123'),
        role='principal',
        full_name='Principal Office',
        active=True,
        password_changed_at=None
    )

    admin_elec_plumb = User(
        username='NT069',
        registration_number='NT069',
        email='nt069@college.com',
        password=generate_password_hash('NT069'),
        role='admin',
        department='Electrical/Plumbing',
        full_name='Admin Electrical & Plumbing',
        active=True,
        password_changed_at=None
    )

    hod_cse = User(
        username='TS182',
        registration_number='TS182',
        email='ts182@college.com',
        password=generate_password_hash('TS182'),
        role='admin',
        department='Computer Science and Engineering',
        full_name='HOD Computer Science and Engineering',
        active=True,
        password_changed_at=None
    )

    hod_me = User(
        username='TS176',
        registration_number='TS176',
        email='ts176@college.com',
        password=generate_password_hash('TS176'),
        role='admin',
        department='Mechanical Engineering',
        full_name='HOD Mechanical Engineering',
        active=True,
        password_changed_at=None
    )
    hod_aids = User(
        username='TS057',
        registration_number='TS057',
        email='ts057@college.com',
        password=generate_password_hash('TS057'),
        role='admin',
        department='Artificial Intelligence and Data Science Engineering',
        full_name='HOD Artificial Intelligence and Data Science Engineering',
        active=True,
        password_changed_at=None
    )
    hod_ece = User(
        username='TS400',
        registration_number='TS400',
        email='ts400@college.com',
        password=generate_password_hash('TS400'),
        role='admin',
        department='Electronics and Communication Engineering',
        full_name='HOD Electronics and Communication Engineering',
        active=True,
        password_changed_at=None
    )
    hod_eee = User(
        username='TS442',
        registration_number='TS442',
        email='ts442@college.com',
        password=generate_password_hash('TS442'),
        role='admin',
        department='Electrical and Electronics Engineering',
        full_name='HOD Electrical and Electronics Engineering',
        active=True,
        password_changed_at=None
    )
    hod_ce = User(
        username='TS387',
        registration_number='TS387',
        email='ts387@college.com',
        password=generate_password_hash('TS387'),
        role='admin',
        department='Civil Engineering',
        full_name='HOD Civil Engineering',
        active=True,
        password_changed_at=None
    )
    hod_as_h = User(
        username='TS468',
        registration_number='TS468',
        email='ts468@college.com',
        password=generate_password_hash('TS468'),
        role='admin',
        department='Applied Science and Humanities Engineering',
        full_name='HOD Applied Science and Humanities Engineering',
        active=True,
        password_changed_at=None
    )

    db.session.add_all([principal, admin_elec_plumb, hod_cse, hod_me, hod_aids, hod_ece, hod_eee, hod_ce, hod_as_h])
    db.session.commit()
    print("[OK] Essential management accounts created!")
    print("[OK] Sample users created!")


if __name__ == '__main__':
    # When running directly, instantiate app and run
    app = create_app()
    init_db(app)

    # Run development server
    port = int(os.environ.get('PORT', 5000))
    debug = get_config().DEBUG
    app.run(host='0.0.0.0', port=port, debug=debug)
