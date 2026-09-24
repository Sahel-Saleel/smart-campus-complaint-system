# smart-campus-complaint-system
  # Complaint Management System - Complete Setup Guide

A comprehensive college complaint management system with role-based access control, confidential complaint handling, upvoting system, and audit logging.

## Features

✅ **Multi-role System**
- Student: Submit and track complaints
- Worker/Staff: View and work on complaints for their department
- Admin: Manage complaints for their department
- Principal: Access confidential complaints with full audit logging

✅ **Complaint Management**
- Submit complaints with title, description, category, priority
- Auto-routing to appropriate department/principal
- Real-time status tracking
- Search and filter functionality
- Edit/delete complaints before resolution

✅ **Confidential System**
- Ragging and Drug Abuse complaints routed directly to Principal only
- Anonymous submission option
- Identity hidden in UI but stored in database
- Full audit logging of all access

✅ **Upvoting System**
- Users can upvote complaints to increase visibility
- Prevent duplicate upvotes (UNIQUE constraint)
- Auto-priority upgrade based on upvote count
- View list of upvoters

✅ **Notifications**
- Real-time notifications for status changes
- Department assignment notifications
- In-app notification center with pagination
- Mark as read/delete functionality

✅ **Security Features**
- Password hashing with werkzeug.security
- Session-based authentication with 30-minute timeout
- Role-based access control (RBAC)
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via template escaping
- Audit logging for confidential access

## Tech Stack

- **Backend**: Python 3.7+ with Flask 2.3.3
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **ORM**: SQLAlchemy 3.0.5

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:
- Flask==2.3.3
- Flask-CORS==4.0.0
- Flask-SQLAlchemy==3.0.5
- Werkzeug==2.3.7

### 2. Run the Application

```bash
python app.py
```

The application will:
- Create the SQLite database automatically
- Initialize tables
- Create sample users for testing
- Start the server at `http://localhost:5000`

### 3. Access the System

Open your browser and navigate to: **http://localhost:5000**

## Demo Credentials

### Student Account
- **Username**: student1
- **Password**: student123
- **Role**: Student

### Admin Account
- **Username**: admin_electrical
- **Password**: admin123
- **Role**: Admin (Electrical Department)

### Principal Account
- **Username**: principal
- **Password**: principal123
- **Role**: Principal

## Project Structure

```
├── app.py                          # Flask app initialization
├── database.py                     # SQLAlchemy models
├── requirements.txt                # Python dependencies
├── routes/
│   ├── __init__.py
│   ├── auth.py                    # Login, register, logout
│   ├── complaints.py              # Complaint submission and viewing
│   ├── admin.py                   # Admin dashboard
│   ├── principal.py               # Confidential complaints
│   └── notifications.py           # Notifications API
├── utils/
│   ├── decorators.py              # Role-based access control
│   └── helpers.py                 # Helper functions
├── templates/
│   ├── base.html                  # Base template with nav
│   ├── login.html
│   ├── register.html
│   ├── student_dashboard.html
│   ├── worker_dashboard.html
│   ├── admin_dashboard.html
│   ├── principal_dashboard.html
│   ├── submit_complaint.html
│   ├── view_complaint.html
│   ├── edit_complaint.html
│   ├── view_confidential_complaint.html
│   ├── notifications.html
│   ├── audit_log.html
│   └── error.html
├── static/
│   ├── css/
│   │   └── style.css              # Global styling
│   └── js/
│       └── utils.js               # JavaScript utilities
└── instance/
    └── complaint_system.db        # SQLite database (auto-created)
```

## Key Endpoints

### Authentication
- `GET/POST /login` - User login
- `GET/POST /register` - New user registration
- `GET /logout` - User logout

### Complaints
- `GET /complaints/dashboard/student` - Student dashboard
- `GET /submit-complaint` - Complaint submission form
- `POST /submit-complaint` - Submit new complaint
- `GET /complaints/<id>` - View complaint details
- `GET /complaints/<id>/edit` - Edit complaint
- `POST /complaints/<id>/delete` - Delete complaint
- `POST /api/complaints/<id>/upvote` - Upvote complaint
- `POST /api/complaints/<id>/upvote/remove` - Remove upvote

### Admin
- `GET /admin/dashboard` - Admin dashboard
- `PUT /api/complaints/<id>/status` - Update complaint status
- `PUT /api/complaints/<id>/priority` - Update priority
- `PUT /api/complaints/<id>/remarks` - Add remarks

### Principal
- `GET /principal/dashboard` - Principal dashboard (confidential)
- `GET /principal/confidential` - View confidential complaints
- `GET /principal/audit-log` - View audit log
- `PUT /api/confidential/<id>/status` - Update status
- `POST /api/confidential/<id>/reveal-identity` - Reveal anonymous complaint

### Notifications
- `GET /notifications` - Notifications page
- `GET /api/notifications` - Get notifications (JSON)
- `PUT /api/notifications/<id>/read` - Mark as read
- `DELETE /api/notifications/<id>` - Delete notification

## Database Schema

### Users Table
- Stores user credentials, role, department
- Roles: student, worker, admin, principal
- Password hashed with werkzeug

### Complaints Table
- Core complaint data
- Status: Pending, In Progress, Resolved
- Priority: Low, Medium, High
- Confidential flag for Ragging/Drug Abuse
- Upvote counter

### Upvotes Table
- Tracks who upvoted what
- UNIQUE constraint prevents duplicate votes
- Auto-increments priority when upvotes > threshold

### Notifications Table
- Stores in-app notifications
- Types: new_complaint, status_changed, assigned, upvoted
- is_read flag for tracking

### Audit Logs Table
- Logs all principal access to confidential data
- Tracks status updates and remarks
- For security and compliance

## Usage Workflow

### For Students
1. **Register** as Student at `/register`
2. **Login** with Student credentials
3. **Submit Complaint** - Click "Submit New Complaint"
   - Select category (routed automatically)
   - Choose priority
   - For Ragging/Drug Abuse: Mark as confidential/anonymous
4. **Track Status** - View on dashboard
5. **Upvote Complaints** - Support important complaints
6. **Receive Notifications** - Get updates on status changes

### For Admin/Department
1. **Login** as Admin with department credentials
2. **View Dashboard** - See complaints for your department
3. **Filter & Sort** - By status, priority, or upvotes
4. **Update Status** - Change from Pending → In Progress → Resolved
5. **Add Remarks** - Provide feedback to students
6. **Manage Upvotes** - Track support level

### For Principal
1. **Login** as Principal
2. **View Confidential** - Access Ragging/Drug Abuse complaints
3. **Audit Log** - See who accessed what and when
4. **Manage Cases** - Update status and add remarks
5. **Reveal Identity** - See anonymous complainant if needed
6. **Track Trends** - Monitor complaint patterns

## Security Considerations

### Authentication
- Passwords hashed using werkzeug.security.generate_password_hash()
- Session timeout: 30 minutes of inactivity
- CSRF protection on all forms
- Secure session cookies (HttpOnly, SameSite=Lax)

### Authorization
- Role-based access control via decorators
- @login_required - Check authentication
- @role_required('admin') - Check role
- @principal_required - Principal-only access
- Department isolation for admin/worker

### Data Protection
- SQLAlchemy ORM prevents SQL injection
- Jinja2 template escaping prevents XSS
- Audit logging for compliance
- Anonymous complaints: hidden UI, stored DB
- Confidential access fully logged

## Customization Guide

### Adding New Categories
Edit `utils/helpers.py`:
```python
CATEGORY_ROUTING = {
    'Your Category': 'Department Name',
    ...
}

CONFIDENTIAL_CATEGORIES = ['Ragging', 'Drug Abuse', 'YourCategory']
```

### Changing Session Timeout
Edit `app.py`:
```python
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Change duration
```

### Styling
Edit `static/css/style.css` for color scheme, fonts, and layout.

### Database
All data stored in `instance/complaint_system.db`. Delete to reset (will recreate on next run).

## Troubleshooting

### Port Already in Use
```bash
# Change port in app.py:
app.run(host='0.0.0.0', port=5001, debug=True)
```

### Database Issues
```bash
# Delete the database to reset
rm instance/complaint_system.db
# Run app.py again - it will recreate
```

### Login Issues
- Check username/password exactly
- User account must be active
- Role selected must match user's role

### Notifications Not appearing
- Check user is logged in
- Notifications require recipient to view page
- Mark as read to clear unread badge

## Testing Workflow

1. **Register new accounts** with different roles
2. **Create complaints** as student with different categories
3. **Check routing** - Admin sees their department
4. **Test upvoting** - Multiple users upvote same complaint
5. **Update status** - Admin changes status, student receives notification
6. **Test confidential** - Submit Ragging complaint, verify only Principal sees it
7. **Check audit log** - Principal access logged

## Performance Tips

- Database is SQLite (in-memory faster but data loss on restart)
- For production, upgrade to PostgreSQL
- Add database indexing on frequently searched columns
- Implement Redis for notifications (future enhancement)
- Enable response caching for static files

## Future Enhancements

- Email notifications for status changes
- WebSocket support for real-time notifications
- Complaint attachments/image upload
- Analytics dashboard for management
- SMS notifications for Principal
- Multi-language support
- Dark mode
- Mobile app

## API Response Format

All API endpoints return JSON responses:

### Success Response
```json
{
    "success": true,
    "message": "Operation successful",
    "data": { ... }
}
```

### Error Response
```json
{
    "success": false,
    "error": "Description of error"
}
```

## License

Educational use - College Complaint Management System

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review database schema in database.py
3. Check browser console for JavaScript errors
4. Review Flask logs for backend errors

---

**Created**: 2024
**Version**: 1.0
**Status**: Production Ready ✓
