# Hostinger VPS Deployment Guide
## Veteran-Employer Job Portal

This guide will walk you through deploying your veteran-employer job portal to your Hostinger VPS with Gunicorn (no Nginx/Docker).

---

## Prerequisites

- SSH access to your Hostinger VPS
- Domain: `vetjobportal.com` pointed to your VPS IP
- Fresh PostgreSQL database on VPS
- Python 3.11+ installed on VPS

---

## Step 1: Upload Files to VPS

### Option A: Using SCP (Recommended)
```bash
# Compress your project locally
tar -czf vetjob-portal.tar.gz .

# Upload to VPS
scp vetjob-portal.tar.gz root@your-vps-ip:/var/www/

# SSH into VPS and extract
ssh root@your-vps-ip
cd /var/www/
tar -xzf vetjob-portal.tar.gz
mv . vetjobportal/
cd vetjobportal/
```

### Option B: Using Git (Alternative)
```bash
ssh root@your-vps-ip
cd /var/www/
git clone https://github.com/yourusername/vetjob-portal.git vetjobportal
cd vetjobportal/
```

---

## Step 2: Install Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install Python and pip if not installed
apt install python3 python3-pip python3-venv postgresql-client -y

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# If requirements.txt doesn't exist, install manually:
pip install flask flask-sqlalchemy flask-login flask-migrate gunicorn psycopg2-binary requests sendgrid twilio werkzeug email-validator
```

---

## Step 3: Set Environment Variables

Create your environment file:

```bash
nano .env
```

Add the following content:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/vetjobportal_db

# Flask Configuration
SESSION_SECRET=your-super-secret-session-key-change-this-in-production
FLASK_ENV=production

# Payment Gateway Configuration
PAYMENT_GATEWAY=paystack
# OR: PAYMENT_GATEWAY=flutterwave

# Paystack Keys
PAYSTACK_PUBLIC_KEY=pk_live_your_actual_paystack_public_key
PAYSTACK_SECRET_KEY=sk_live_your_actual_paystack_secret_key

# Flutterwave Keys
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK-your_actual_flutterwave_public_key
FLUTTERWAVE_SECRET_KEY=FLWSECK-your_actual_flutterwave_secret_key

# Email Configuration (Optional)
SENDGRID_API_KEY=your_sendgrid_api_key
FROM_EMAIL=noreply@vetjobportal.com
FROM_NAME=Veteran Job Portal

# SMS Configuration (Optional)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

Load environment variables:
```bash
export $(cat .env | xargs)
```

---

## Step 4: Database Setup

### Create PostgreSQL Database
```bash
# Login to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE vetjobportal_db;
CREATE USER vetjob_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE vetjobportal_db TO vetjob_user;
\q
```

### Run Database Migrations
```bash
# Initialize Flask-Migrate (if migrations folder doesn't exist)
flask db init

# Create migration
flask db migrate -m "Initial migration"

# Apply migrations
flask db upgrade
```

---

## Step 5: Create First Admin Account

Run the admin creation script:

```bash
python create_admin.py
```

Follow the prompts to:
- Enter admin email
- Set admin password (minimum 8 characters)
- Confirm password
- Enter admin first/last name

Example interaction:
```
=== Veteran-Employer Job Portal Admin Setup ===
Enter admin email: admin@vetjobportal.com
Enter admin password (min 8 characters): AdminPass123!
Confirm admin password: AdminPass123!
Enter admin first name: John
Enter admin last name: Admin

✅ Admin account created successfully!
```

---

## Step 6: Test the Application

Test that everything works:

```bash
# Test with Python directly
python wsgi.py

# Test with Gunicorn
gunicorn -w 1 -b 0.0.0.0:8000 wsgi:app
```

Visit `http://your-vps-ip:8000` to verify the app loads.

---

## Step 7: Production Deployment

### Create Systemd Service

Create service file:
```bash
nano /etc/systemd/system/vetjobportal.service
```

Add this content:
```ini
[Unit]
Description=Veteran Job Portal Flask App
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/var/www/vetjobportal
Environment="PATH=/var/www/vetjobportal/venv/bin"
EnvironmentFile=/var/www/vetjobportal/.env
ExecStart=/var/www/vetjobportal/venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### Start the Service

```bash
# Reload systemd
systemctl daemon-reload

# Start the service
systemctl start vetjobportal

# Enable auto-start on boot
systemctl enable vetjobportal

# Check status
systemctl status vetjobportal
```

---

## Step 8: Domain Configuration

### Point Domain to VPS
1. In your domain registrar, point `vetjobportal.com` to your VPS IP
2. Create A record: `vetjobportal.com` → `your-vps-ip`
3. Create CNAME record: `www.vetjobportal.com` → `vetjobportal.com`

### Configure Firewall
```bash
# Allow SSH, HTTP, and custom port
ufw allow 22
ufw allow 80
ufw allow 8000
ufw enable
```

---

## Step 9: Access Your Application

### URLs to Test:
- **Main Site**: `http://vetjobportal.com:8000`
- **Admin Login**: `http://vetjobportal.com:8000/login`
- **Admin Dashboard**: `http://vetjobportal.com:8000/admin`

### Admin Configuration Steps:

1. **Login** with your admin account
2. **Go to Admin → Settings** to configure payment gateways:
   - Choose between Paystack or Flutterwave
   - Enter your API keys
   - Set test/live mode
   - Configure pricing

3. **Test payment functionality**:
   - Create test veteran account
   - Try verification payment
   - Check admin revenue analytics

---

## Step 10: Optional Production Optimizations

### SSL Certificate (Recommended)
```bash
# Install Certbot
apt install certbot -y

# Get SSL certificate
certbot certonly --standalone -d vetjobportal.com -d www.vetjobportal.com

# Update service to use HTTPS (requires additional Nginx setup)
```

### Performance Monitoring
```bash
# View application logs
journalctl -u vetjobportal -f

# Monitor system resources
htop

# Check application status
systemctl status vetjobportal
```

### Backup Strategy
```bash
# Database backup script
pg_dump vetjobportal_db > backup_$(date +%Y%m%d).sql

# Create daily backup cron job
crontab -e
# Add: 0 2 * * * pg_dump vetjobportal_db > /backups/vetjob_$(date +\%Y\%m\%d).sql
```

---

## Troubleshooting

### Common Issues:

**App won't start:**
```bash
# Check logs
journalctl -u vetjobportal -n 50

# Check if port is in use
netstat -tulpn | grep 8000

# Test manually
cd /var/www/vetjobportal
source venv/bin/activate
python wsgi.py
```

**Database connection errors:**
```bash
# Test database connection
psql -h localhost -U vetjob_user -d vetjobportal_db

# Check DATABASE_URL format
echo $DATABASE_URL
```

**Payment gateway errors:**
- Verify API keys in admin settings
- Check payment gateway mode (test/live)
- Review application logs for payment errors

**Permission errors:**
```bash
# Fix file permissions
chown -R www-data:www-data /var/www/vetjobportal
chmod -R 755 /var/www/vetjobportal
```

---

## Success Checklist

- [ ] Application accessible at `http://vetjobportal.com:8000`
- [ ] Admin login working
- [ ] Database connection successful
- [ ] Payment gateway configured
- [ ] Test transactions working
- [ ] Service auto-starts on reboot
- [ ] Logs are accessible and clean

---

## Support

If you encounter issues:
1. Check application logs: `journalctl -u vetjobportal -f`
2. Verify all environment variables are set
3. Test database connectivity
4. Ensure all dependencies are installed

Your veteran-employer job portal is now live! 🎉