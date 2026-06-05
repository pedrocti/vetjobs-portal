import requests
import os

API_KEY = os.environ.get("BREVO_API_KEY")

def send_email(to_email, to_name, subject, html_content):
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "content-type": "application/json", "api-key": API_KEY}
    payload = {"sender": {"name": "VetJobPortal Team", "email": "support@vetjobportal.com"}, "to": [{"email": to_email, "name": to_name}], "subject": subject, "htmlContent": html_content}
    r = requests.post(url, headers=headers, json=payload)
    return r.status_code, r.text

no_docs = [
    {"email": "kogb91@gmail.com", "name": "Veteran"},
    {"email": "umaruinusa66@gmail.com", "name": "Veteran"},
    {"email": "olybrown56@gmail.com", "name": "Veteran"},
    {"email": "gbisejack@gmail.com", "name": "Veteran"},
    {"email": "a4t4eva2011@gmail.com", "name": "Veteran"},
    {"email": "daddyboy153@gmail.com", "name": "Veteran"},
    {"email": "calistusemeka308@gmail.com", "name": "Calistus"},
    {"email": "alexnwa007@gmail.com", "name": "Nwachukwu"},
    {"email": "rotexoguns@gmail.com", "name": "Rotimi"},
]

missing_discharge = [
    {"email": "oladipo181.ooa@gmail.com", "name": "Oladipo"},
]

def html_no_docs(name):
    return "<div style='font-family:Arial;max-width:600px;margin:0 auto'><div style='background:#0D1B3E;padding:24px;text-align:center'><h1 style='color:#D4AF37;margin:0'>VETJOBPORTAL</h1><p style='color:#fff;font-size:13px'>Nigeria's First Verified Military Veteran Talent Platform</p></div><div style='padding:32px 24px'><p>Dear " + name + ",</p><p>Thank you for registering on VetJobPortal.</p><p>We reviewed your account and were unable to approve it at this time. Your profile is currently <strong>missing all required verification documents.</strong></p><div style='background:#FADBD8;border-left:4px solid #C0392B;padding:16px;margin:20px 0'><p style='color:#C0392B;margin:0;font-weight:bold'>Your profile is invisible to employers until documents are uploaded.</p></div><p>To activate your account you must upload the following:</p><ol><li><strong>Military Discharge Certificate</strong></li><li><strong>Retired Military ID Card</strong></li><li><strong>CV or Resume</strong></li><li><strong>Valid ID - NIN or International Passport</strong></li></ol><p>Log in at <a href='https://vetjobportal.com' style='color:#0D1B3E'>vetjobportal.com</a>, go to your profile and upload all documents. Your account will be activated within 24 hours.</p><p>Employers are actively reviewing verified veteran profiles on our platform right now. Do not miss this opportunity.</p><p>If you need any assistance reply to this email and we will guide you directly.</p><p>Warm regards,<br><strong>VetJobPortal Team</strong><br>support@vetjobportal.com | vetjobportal.com</p></div><div style='background:#0D1B3E;padding:16px;text-align:center'><p style='color:#D4AF37;margin:0;font-size:12px'>Built by veterans. For veterans. | vetjobportal.com</p></div></div>"

def html_missing_discharge(name):
    return "<div style='font-family:Arial;max-width:600px;margin:0 auto'><div style='background:#0D1B3E;padding:24px;text-align:center'><h1 style='color:#D4AF37;margin:0'>VETJOBPORTAL</h1><p style='color:#fff;font-size:13px'>Nigeria's First Verified Military Veteran Talent Platform</p></div><div style='padding:32px 24px'><p>Dear " + name + ",</p><p>Thank you for registering on VetJobPortal and uploading your documents.</p><p>We reviewed your account and were unable to approve it at this time. Your profile is missing one critical document:</p><div style='background:#FADBD8;border-left:4px solid #C0392B;padding:16px;margin:20px 0'><p style='color:#C0392B;margin:0;font-weight:bold'>Missing: Military Discharge Certificate</p></div><p>This document is required to verify your military service. Without it your profile remains invisible to employers currently searching for candidates on our platform.</p><p>Log in at <a href='https://vetjobportal.com' style='color:#0D1B3E'>vetjobportal.com</a>, go to your profile and upload your Discharge Certificate. Your account will be activated within 24 hours.</p><p>If you need any assistance reply to this email directly.</p><p>Warm regards,<br><strong>VetJobPortal Team</strong><br>support@vetjobportal.com | vetjobportal.com</p></div><div style='background:#0D1B3E;padding:16px;text-align:center'><p style='color:#D4AF37;margin:0;font-size:12px'>Built by veterans. For veterans. | vetjobportal.com</p></div></div>"

print("=" * 50)
print("Sending verification emails to veterans...")
print("=" * 50)

for vet in no_docs:
    s, r = send_email(vet["email"], vet["name"], "Your VetJobPortal Account — Action Required to Complete Verification", html_no_docs(vet["name"]))
    print(f"{'✓' if s == 201 else '✗'} {vet['email']} — {'SENT' if s == 201 else r}")

for vet in missing_discharge:
    s, r = send_email(vet["email"], vet["name"], "Your VetJobPortal Account — Discharge Certificate Required", html_missing_discharge(vet["name"]))
    print(f"{'✓' if s == 201 else '✗'} {vet['email']} — {'SENT' if s == 201 else r}")

print("=" * 50)
print("Done.")
print("=" * 50)
