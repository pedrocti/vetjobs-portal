import requests
import os

API_KEY = os.environ.get("BREVO_API_KEY")

def send_email(to_email, to_name, subject, html_content):
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "content-type": "application/json", "api-key": API_KEY}
    payload = {"sender": {"name": "Pedro Isong | VetJobPortal", "email": "support@vetjobportal.com"}, "to": [{"email": to_email, "name": to_name}], "subject": subject, "htmlContent": html_content}
    r = requests.post(url, headers=headers, json=payload)
    return r.status_code, r.text

html1 = "<div style='font-family:Arial;max-width:600px;margin:0 auto'><div style='background:#0D1B3E;padding:24px;text-align:center'><h1 style='color:#D4AF37;margin:0'>VETJOBPORTAL</h1><p style='color:#fff;font-size:13px'>Nigeria's First Verified Military Veteran Talent Platform</p></div><div style='padding:32px 24px'><p>Dear Veteran,</p><p>Thank you for registering on VetJobPortal.</p><p>We reviewed your account and were unable to approve it. Your profile is <strong>missing all required verification documents.</strong></p><div style='background:#FADBD8;border-left:4px solid #C0392B;padding:16px;margin:20px 0'><p style='color:#C0392B;margin:0;font-weight:bold'>Your profile is invisible to employers until documents are uploaded.</p></div><p>To activate your account upload the following:</p><ol><li><strong>Military Discharge Certificate</strong></li><li><strong>CV or Resume</strong></li><li><strong>Valid ID - NIN or International Passport</strong></li></ol><p>Log in at <a href='https://vetjobportal.com'>vetjobportal.com</a>, go to your profile and upload all three documents. Your account will be activated within 24 hours.</p><p>Employers are actively reviewing verified profiles right now. Do not miss this opportunity.</p><p>Warm regards,<br><strong>Pedro Isong</strong><br>Founder, VetJobPortal<br>support@vetjobportal.com | vetjobportal.com</p></div><div style='background:#0D1B3E;padding:16px;text-align:center'><p style='color:#D4AF37;margin:0;font-size:12px'>Built by veterans. For veterans. | vetjobportal.com</p></div></div>"

html2 = "<div style='font-family:Arial;max-width:600px;margin:0 auto'><div style='background:#0D1B3E;padding:24px;text-align:center'><h1 style='color:#D4AF37;margin:0'>VETJOBPORTAL</h1><p style='color:#fff;font-size:13px'>Nigeria's First Verified Military Veteran Talent Platform</p></div><div style='padding:32px 24px'><p>Dear Oladipo,</p><p>Thank you for registering on VetJobPortal and uploading your documents.</p><p>We reviewed your account and were unable to approve it. Your profile is missing one critical document:</p><div style='background:#FADBD8;border-left:4px solid #C0392B;padding:16px;margin:20px 0'><p style='color:#C0392B;margin:0;font-weight:bold'>Missing: Military Discharge Certificate</p></div><p>This document is required to verify your military service. Without it your profile remains invisible to employers.</p><p>Log in at <a href='https://vetjobportal.com'>vetjobportal.com</a>, go to your profile and upload your Discharge Certificate. Your account will be activated within 24 hours.</p><p>Warm regards,<br><strong>Pedro Isong</strong><br>Founder, VetJobPortal<br>support@vetjobportal.com | vetjobportal.com</p></div><div style='background:#0D1B3E;padding:16px;text-align:center'><p style='color:#D4AF37;margin:0;font-size:12px'>Built by veterans. For veterans. | vetjobportal.com</p></div></div>"

print("Sending test emails...")
s1, r1 = send_email("support@vetjobportal.com", "Pedro", "TEST 1 — Account Verification Required", html1)
print(f"Test 1: {s1} — {'SENT' if s1 == 201 else r1}")

s2, r2 = send_email("support@vetjobportal.com", "Pedro", "TEST 2 — Discharge Certificate Required", html2)
print(f"Test 2: {s2} — {'SENT' if s2 == 201 else r2}")
