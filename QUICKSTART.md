# Quick Start Guide - Complaint Management System

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run the Application
```bash
python app.py
```

### Step 3: Open in Browser
```
http://localhost:5000
```

---

## 📋 Test Accounts (Pre-created)

| Role | Username | Password | Department |
|------|----------|----------|-----------|
| 👤 Student | `student1` | `student123` | - |
| 👤 Student | `student2` | `student123` | - |
| 🛠️ Worker | `worker1` | `worker123` | Plumbing |
| 👨‍💼 Admin | `admin_electrical` | `admin123` | Electrical |
| 👑 Principal | `principal` | `principal123` | - |

---

## 🎯 What to Test

### 1. Student Workflow (student1)
1. Login with `student1` / `student123`
2. Click "Submit New Complaint"
3. Fill the form:
   - Title: "Classroom lights not working"
   - Category: "Electrical"
   - Priority: "High"
   - Click Submit
4. View complaint on dashboard
5. Try to upvote (will fail - can't upvote own)
6. Logout

### 2. Admin Workflow (admin_electrical)
1. Login with `admin_electrical` / `admin123`
2. See all Electrical department complaints
3. Click on complaint from student1
4. Update status: "In Progress"
5. Add remarks: "Electrician assigned for Monday"
6. Student receives notification!

### 3. Confidential Complaint (student2)
1. Login with `student2` / `student123`
2. Submit complaint:
   - Title: "Bullying incident"
   - Category: "Ragging"  ← Notice it becomes confidential
   - Anonymous: Check this box
3. Logout
4. Login as Principal
5. Only principal sees it in confidential tab
6. Check audit log - access logged!

### 4. Upvoting System (Any student)
1. Login with `student1`
2. View another student's complaint
3. Click "👍 Upvote"
4. Try again - blocked (duplicate prevention works!)
5. Count increases
6. Click "View Upvoters" - see who upvoted

### 5. Notifications
1. Submit complaint as student
2. Admin updates status
3. Check notification bell - unread count shows!
4. Click bell → See notifications page
5. Click notification → Goes to complaint

---

## 📁 Project Structure

```
complaint_management/
├── app.py                 # Run this to start
├── database.py            # Database models
├── requirements.txt       # Dependencies
├── routes/                # API endpoints
│   ├── auth.py           # Login/Register
│   ├── complaints.py     # Complaints CRUD
│   ├── admin.py          # Admin management
│   ├── principal.py      # Confidential + Audit
│   └── notifications.py  # Notifications
├── utils/
│   ├── decorators.py     # Access control
│   └── helpers.py        # Helper functions
├── templates/            # HTML pages
├── static/              # CSS & JS
└── README.md            # Full documentation
```

---

## 🔒 Key Features Explained

### Confidential Complaints
- **Ragging** and **Drug Abuse** auto-routed to Principal ONLY
- Anonymous option: UI shows `[Anonymous User]`, DB stores real ID
- All access logged to audit log for compliance

### Upvote System
- Users can upvote (except own complaints)
- UNIQUE database constraint prevents duplicates
- Auto-increases priority: 10+ = Medium, 25+ = High
- Can't upvote confidential complaints

### Department Routing
- **Electrical** → admin_electrical
- **Plumbing** → worker/admin for Plumbing
- **Hostel** → Hostel admin
- **Academic** → Academic coordinator
- **Cleaning** → Maintenance
- **Ragging** → Principal only (Confidential)
- **Drug Abuse** → Principal only (Confidential)

### Notifications
- Users notified when assigned
- Users notified when status changes
- Principal notified of confidential submissions
- View history in notifications page

---

## 🐛 Troubleshooting

### "Port 5000 already in use"
```bash
# Use different port
python app.py  # Edit app.py, change port=5001
```

### "Module not found"
```bash
# Install dependencies
pip install -r requirements.txt
```

### "Database locked"
```bash
# Delete database to reset
rm instance/complaint_system.db
# Run app.py again
```

### Reset Everything
```bash
# Remove database
rm instance/complaint_system.db

# Install dependencies fresh
pip install --force-reinstall -r requirements.txt

# Run app
python app.py
```

---

## 📊 Test Matrix

| Feature | Test With | Expected Result |
|---------|-----------|-----------------|
| **Submit Complaint** | student1 | Creates & routes to admin |
| **Upvote** | student2 | Increases count, notifies creator |
| **Duplicate Upvote** | student2 | "Already upvoted" error |
| **Confidential** | student1 → Ragging | Only principal sees |
| **Anonymous** | student1 → Drug Abuse | Shows [Anonymous] to principal |
| **Status Update** | admin_electrical | Notifies student |
| **Audit Log** | principal | Logs access time & user |
| **Department Isolation** | admin_electrical | Only sees Electrical |

---

## 🎓 Learning the Code

### Start Reading Here:
1. `app.py` - Main entry point, app config
2. `database.py` - Table structure & relationships
3. `routes/auth.py` - Session management
4. `routes/complaints.py` - CRUD operations
5. `utils/decorators.py` - Access control
6. `utils/helpers.py` - Business logic

### Key Patterns:
- **RBAC**: Use `@role_required('admin')` decorator
- **ORM**: Use SQLAlchemy for database queries
- **Validation**: Put in `utils/helpers.py`
- **Templates**: Extend `base.html` for consistent UI

---

## 📚 Full Documentation

See `README.md` for:
- Complete setup guide
- All API endpoints
- Database schema details
- Customization guide
- Performance tips
- Future enhancements

---

## ✅ Success Indicators

You'll know it's working when:

✓ App starts without errors
✓ Can login with demo accounts
✓ Can submit complaints
✓ Each user sees appropriate data
✓ Status changes generate notifications
✓ Confidential complaints hidden from non-principals
✓ Upvote prevents duplicates
✓ Audit log records principal access

---

**Ready to run?**
```bash
pip install -r requirements.txt
python app.py
```

Then navigate to: **http://localhost:5000**

Enjoy! 🎉
