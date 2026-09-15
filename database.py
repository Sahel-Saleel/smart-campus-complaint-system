"""
Database Models for Complaint Management System
Defines all SQLAlchemy models with proper indexing, relationships, and tracking fields.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()


def generate_uuid():
    """Generate a unique string UUID."""
    return str(uuid.uuid4())


# ========== USER MODEL ==========
class User(db.Model):
    """User model for all system users including auth tracking and locking properties."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), default=generate_uuid, unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)  # 'student', 'worker', 'admin', 'principal'
    department = db.Column(db.String(100), index=True)  # For admin/worker only
    registration_number = db.Column(db.String(50), unique=True, nullable=True, index=True)  # Unique Student Reg Number
    phone = db.Column(db.String(20), nullable=True)
    
    # Auth locking & tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime, nullable=True)
    password_changed_at = db.Column(db.DateTime, nullable=True)
    login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)

    # Relationships
    complaints = db.relationship('Complaint', foreign_keys='Complaint.user_id', backref='creator')
    upvotes = db.relationship('Upvote', backref='user', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='recipient', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', cascade='all, delete-orphan')
    assigned_complaints = db.relationship('Complaint', foreign_keys='Complaint.assigned_to', backref='assigned_admin')

    # Indexes and constraints
    __table_args__ = (
        db.Index('idx_user_role_dept', 'role', 'department'),
    )

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

    def is_admin(self):
        """Check if user is admin or principal"""
        return self.role in ['admin', 'principal']

    def is_principal(self):
        """Check if user is principal"""
        return self.role == 'principal'

    @property
    def is_authenticated(self):
        """Check if user is authenticated"""
        return True

    @property
    def is_first_login(self):
        """Check if user has not completed first login setup (password_changed_at is None)"""
        return self.password_changed_at is None

    @is_first_login.setter
    def is_first_login(self, value):
        """Set onboarding status"""
        if value:
            self.password_changed_at = None
        elif self.password_changed_at is None:
            self.password_changed_at = datetime.utcnow()

    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'uuid': self.uuid,
            'username': self.username,
            'full_name': self.full_name,
            'email': self.email,
            'role': self.role,
            'department': self.department,
            'registration_number': self.registration_number,
            'phone': self.phone,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M:%S') if self.last_login else None
        }


# ========== COMPLAINT MODEL ==========
class Complaint(db.Model):
    """Complaint model for all submitted complaints"""
    __tablename__ = 'complaints'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False, index=True)
    priority = db.Column(db.String(20), default='Low', index=True)  # 'Low', 'Medium', 'High'
    status = db.Column(db.String(20), default='Pending', index=True)  # 'Pending', 'In Progress', 'Resolved'
    is_confidential = db.Column(db.Boolean, default=False, index=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    is_overdue = db.Column(db.Boolean, default=False, index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    location = db.Column(db.String(200), nullable=False, default='')
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True, index=True)
    remarks = db.Column(db.Text)
    upvote_count = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    upvotes = db.relationship('Upvote', backref='complaint', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='complaint', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='complaint', cascade='all, delete-orphan')
    supporting_comments = db.relationship('SupportingComment', backref='complaint', cascade='all, delete-orphan')

    # Indexes
    __table_args__ = (
        db.Index('idx_complaints_filtering', 'category', 'status', 'priority'),
    )

    def __repr__(self):
        return f'<Complaint {self.id}: {self.title}>'

    def update_upvote_priority(self):
        """Auto-update priority based on upvote count"""
        if self.upvote_count >= 10:
            self.priority = 'High'
        elif self.upvote_count >= 5:
            self.priority = 'Medium'
        else:
            self.priority = 'Low'

    def get_creator_name(self):
        """Get creator name, respecting anonymity"""
        if self.is_anonymous:
            return '[Anonymous User]'
        if self.creator:
            return self.creator.full_name or self.creator.username
        return 'Unknown'

    def to_dict(self, include_creator_email=False):
        """Convert complaint to dictionary"""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'priority': self.priority,
            'status': self.status,
            'is_confidential': self.is_confidential,
            'is_anonymous': self.is_anonymous,
            'is_overdue': self.is_overdue,
            'location': self.location,
            'is_deleted': self.is_deleted,
            'resolved_at': self.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if self.resolved_at else None,
            'creator_name': self.get_creator_name(),
            'upvote_count': self.upvote_count,
            'remarks': self.remarks,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }
        if include_creator_email:
            data['creator_id'] = self.user_id
        return data


# ========== UPVOTE MODEL ==========
class Upvote(db.Model):
    """Upvote model to track complaint upvotes"""
    __tablename__ = 'upvotes'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Constraint to prevent duplicate upvotes
    __table_args__ = (db.UniqueConstraint('complaint_id', 'user_id', name='unique_complaint_user'),)

    def __repr__(self):
        return f'<Upvote: Complaint {self.complaint_id}, User {self.user_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Unknown',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


# ========== NOTIFICATION MODEL ==========
class Notification(db.Model):
    """Notification model for user alerts"""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), index=True)
    notification_type = db.Column(db.String(50), nullable=False, index=True)  # 'new_complaint', 'status_changed', 'assigned', 'upvoted'
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<Notification {self.id}: {self.notification_type}>'

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.notification_type,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'complaint_id': self.complaint_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


# ========== AUDIT LOG MODEL ==========
class AuditLog(db.Model):
    """Audit log for tracking confidential access and important actions"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), index=True)
    details = db.Column(db.Text)  # Additional context
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<AuditLog {self.id}: {self.action}>'

    def to_dict(self):
        complaint_info = ''
        if self.complaint_id:
            complaint = Complaint.query.get(self.complaint_id)
            if complaint:
                complaint_info = f' - {complaint.title}'

        return {
            'id': self.id,
            'user': self.user.username if self.user else 'Unknown',
            'action': self.action,
            'complaint_id': self.complaint_id,
            'complaint_info': complaint_info,
            'details': self.details,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


# ========== CATEGORY DEPARTMENT MAPPING ==========
class CategoryMapping(db.Model):
    """Map complaint categories to department admins"""
    __tablename__ = 'category_mapping'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __repr__(self):
        return f'<CategoryMapping {self.category}>'

    def to_dict(self):
        department_name = ''
        if self.department_id:
            admin = User.query.get(self.department_id)
            if admin:
                department_name = admin.department or admin.username
        return {
            'category': self.category,
            'department': department_name,
            'department_id': self.department_id
        }


# ========== SUPPORTING COMMENT MODEL ==========
class SupportingComment(db.Model):
    """Supporting comments on existing complaints (for duplicate detection system)"""
    __tablename__ = 'supporting_comments'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    comment = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    user = db.relationship('User', backref='supporting_comments')

    def __repr__(self):
        return f'<SupportingComment {self.id}: Complaint {self.complaint_id}>'

    def get_commenter_name(self):
        """Get commenter name, respecting anonymity"""
        if self.is_anonymous:
            return '[Anonymous]'
        return self.user.username if self.user else 'Unknown'

    def to_dict(self):
        return {
            'id': self.id,
            'complaint_id': self.complaint_id,
            'commenter_name': self.get_commenter_name(),
            'comment': self.comment,
            'is_anonymous': self.is_anonymous,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'commenter_role': self.user.role if self.user else None
        }


# ========== COLLEGE STUDENT DATABASE MODEL ==========
class CollegeStudent(db.Model):
    """Pre-verified college student database for registration validation."""
    __tablename__ = 'college_students'

    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(50), unique=True, nullable=False, index=True)

    def __repr__(self):
        return f'<CollegeStudent {self.registration_number}>'


# ========== PASSWORD RESET REQUESTS MODEL ==========
class PasswordResetRequest(db.Model):
    """Password reset requests submitted by users for admin approval or Email OTP verification."""
    __tablename__ = 'password_reset_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='Pending', index=True)  # 'Pending', 'Approved', 'Rejected', 'Verified'
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationship
    user = db.relationship('User', backref=db.backref('reset_requests', cascade='all, delete-orphan'))

    def is_otp_valid(self, code):
        """Check if provided OTP code matches and is not expired."""
        if not self.otp_code or not self.otp_expiry:
            return False
        if datetime.utcnow() > self.otp_expiry:
            return False
        return str(self.otp_code).strip() == str(code).strip()

    def __repr__(self):
        return f'<PasswordResetRequest {self.id}: User {self.user_id} Status {self.status}>'


