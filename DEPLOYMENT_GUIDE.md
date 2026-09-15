# 🚀 Campus Voice Deployment Guide

This guide provides step-by-step instructions to deploy the **Campus Voice – Smart Campus Complaint Management System** for your college.

---

## 📋 Pre-Deployment Checklist

The codebase is now pre-configured for production deployment:
- ✅ Production entry point: `wsgi.py`
- ✅ Process file: `Procfile` (`web: gunicorn wsgi:app`)
- ✅ Production dependencies added to `requirements.txt` (`gunicorn`, `psycopg2-binary`)

---

## 🌐 Option 1: Deploy to Cloud (Render.com) — *Recommended (Fastest & Free HTTPS)*

Render provides free SSL certificates, automated GitHub deployment, and zero server maintenance.

### Step 1: Push Code to GitHub
1. Create a repository on GitHub (e.g., `campus-voice`).
2. Commit and push all files to GitHub:
   ```bash
   git add .
   git commit -m "Prepare Campus Voice for production deployment"
   git push origin main
   ```

### Step 2: Create a Web Service on Render
1. Sign up/log in at [Render.com](https://render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository (`campus-voice`).

### Step 3: Configure Build & Start Settings
- **Name**: `campus-voice`
- **Region**: Oregon (US) or Singapore (closest to India)
- **Branch**: `main`
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn wsgi:app`

### Step 4: Add Environment Variables
In the **Environment Variables** section on Render, add the following key-value pairs:

| Key | Value | Purpose |
| :--- | :--- | :--- |
| `FLASK_ENV` | `production` | Enables production security mode |
| `SECRET_KEY` | `generate-a-secure-random-32-byte-hex-key` | Session security |
| `DATABASE_URL` | `sqlite:///complaint_system.db` *(or PostgreSQL URL)* | Database storage |
| `MAIL_SERVER` | `smtp.gmail.com` | Email server |
| `MAIL_PORT` | `587` | STARTTLS port |
| `MAIL_USE_TLS` | `true` | Enables TLS |
| `MAIL_USERNAME` | `campusvoicesimat@gmail.com` | SMTP sender email |
| `MAIL_PASSWORD` | `xzsl lvud eeuu iity` | Gmail App Password |
| `MAIL_DEFAULT_SENDER` | `campusvoicesimat@gmail.com` | Sender address |

### Step 5: Deploy & Share
Click **Create Web Service**. Render will build and launch your application, giving you a live URL like:
`https://campus-voice.onrender.com`

---

## 🖥️ Option 2: Deploy to College On-Premise Linux Server (Nginx + Gunicorn)

If your college requires hosting the application locally on the campus data center/server room:

### Step 1: Install System Dependencies
On an Ubuntu 22.04 / 24.04 LTS server:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx git -y
```

### Step 2: Clone and Setup Virtual Environment
```bash
cd /var/www
sudo git clone https://github.com/your-username/campus-voice.git
cd campus-voice
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt
```

### Step 3: Configure Systemd Service (`/etc/systemd/system/campusvoice.service`)
Create the systemd service file:
```ini
[Unit]
Description=Campus Voice Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/campus-voice
Environment="PATH=/var/www/campus-voice/venv/bin"
Environment="FLASK_ENV=production"
Environment="SECRET_KEY=a8f9b2c3d4e5f6g7h8i9j0k1l2m3n4o5"
Environment="DATABASE_URL=sqlite:////var/www/campus-voice/complaint_system.db"
Environment="MAIL_SERVER=smtp.gmail.com"
Environment="MAIL_PORT=587"
Environment="MAIL_USE_TLS=true"
Environment="MAIL_USERNAME=campusvoicesimat@gmail.com"
Environment="MAIL_PASSWORD=xzsl lvud eeuu iity"
Environment="MAIL_DEFAULT_SENDER=campusvoicesimat@gmail.com"

ExecStart=/var/www/campus-voice/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 wsgi:app

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable campusvoice
sudo systemctl start campusvoice
```

### Step 4: Configure Nginx Reverse Proxy (`/etc/nginx/sites-available/campusvoice`)
```nginx
server {
    listen 80;
    server_name campusvoice.college.edu; # Or your server's local IP address

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /var/www/campus-voice/static;
        expires 30d;
    }
}
```

Enable site & reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/campusvoice /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔐 Initial Credentials Summary for College Handover

| Role | Username | Default Password | Initial Action |
| :--- | :--- | :--- | :--- |
| **Principal** | `principal` | `principal123` | Mandatory email linking & password change on first login |
| **HOD Admin (CS)** | `TS182` | `TS182` | Pre-linked to `sahelkunikakath@gmail.com` |
| **Dept Admin (Elec/Plumb)** | `NT069` | `NT069` | Mandatory email linking & password change on first login |

---

## 🎯 Final Note
For presenting to your college authorities, **Option 1 (Render.com)** is the fastest way to get a live, working HTTPS link to demo on laptops, projectors, and mobile devices instantly.
