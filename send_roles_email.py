import smtplib, psycopg2, argparse, time, sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST     = "smtp.hostinger.com"
SMTP_PORT     = 465
SMTP_USER     = "support@vetjobportal.com"
SMTP_PASSWORD = "M8nd8te123@vetjob"
FROM_NAME     = "VetJobPortal"
FROM_EMAIL    = "support@vetjobportal.com"
DB_URL        = "postgresql://vetjobs_user:M8nd8te321@localhost/vetjobs_db"
TEST_EMAIL    = "support@seventy7hub.com"
WHATSAPP_LINK = "https://chat.whatsapp.com/FiXN7lzXYi6IvxjhXMcx2E"
JOBS_URL      = "https://vetjobportal.com/jobs/board"
SUBJECT       = "New Roles Have Been Added and are Live for  Veterans & Military Spouses."
DELAY         = 1.2


def build_html(first_name):
    n = first_name.strip().title() if first_name else "Veteran"
    return """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F4F6F9;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 0;background:#F4F6F9;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

<!-- HEADER -->
<tr><td style="background:#1B2A4A;border-radius:10px 10px 0 0;padding:32px 40px;text-align:center;">
<p style="margin:0 0 8px;font-size:11px;letter-spacing:2px;color:#C8952A;font-weight:700;text-transform:uppercase;">VetJobPortal</p>
<h1 style="margin:0;font-size:24px;font-weight:700;color:#ffffff;line-height:1.3;">New Roles Have Been Added and are Live for  Veterans & Military Spouses.</h1>
<p style="margin:12px 0 0;font-size:14px;color:#9AADC4;">On-site in Nigeria. Remote. Contract. Full-time. Updated every day.</p>
</td></tr>

<!-- BODY -->
<tr><td style="background:#ffffff;padding:36px 40px;">

<p style="margin:0 0 16px;font-size:16px;color:#1A1A1A;line-height:1.6;">Dear """ + n + """,</p>

<p style="margin:0 0 20px;font-size:15px;color:#333333;line-height:1.7;">
The VetJobPortal job board is <strong>live, active, and updated daily</strong> with real opportunities for Nigerian veterans and military spouses — whether you are looking for an on-site role, a remote position, a contract engagement, or full-time employment.
</p>

<!-- ROLE TYPE CARDS -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">
<tr>
<td width="48%" style="background:#F0F4FA;border-radius:8px;padding:18px 20px;vertical-align:top;">
<p style="margin:0 0 6px;font-size:13px;font-weight:700;color:#1B2A4A;">On-Site Roles in Nigeria</p>
<p style="margin:0;font-size:13px;color:#444444;line-height:1.6;">Active positions with Nigerian organisations and companies. New listings added daily. Open to veterans across all service backgrounds and ranks.</p>
</td>
<td width="4%"></td>
<td width="48%" style="background:#F0F4FA;border-radius:8px;padding:18px 20px;vertical-align:top;">
<p style="margin:0 0 6px;font-size:13px;font-weight:700;color:#1B2A4A;">Remote Roles</p>
<p style="margin:0;font-size:13px;color:#444444;line-height:1.6;">Fully remote, international positions available to veterans and military spouses. Work from anywhere in Nigeria with a stable internet connection.</p>
</td>
</tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
<tr>
<td width="48%" style="background:#F0F4FA;border-radius:8px;padding:18px 20px;vertical-align:top;">
<p style="margin:0 0 6px;font-size:13px;font-weight:700;color:#1B2A4A;">Contract Roles</p>
<p style="margin:0;font-size:13px;color:#444444;line-height:1.6;">Short and medium-term contracts suited to veterans who want flexibility without sacrificing structure or income.</p>
</td>
<td width="4%"></td>
<td width="48%" style="background:#F0F4FA;border-radius:8px;padding:18px 20px;vertical-align:top;">
<p style="margin:0 0 6px;font-size:13px;font-weight:700;color:#1B2A4A;">For Military Spouses</p>
<p style="margin:0;font-size:13px;color:#444444;line-height:1.6;">Remote and flexible roles specifically suitable for military spouses. The board is open to you browse, apply, and take the step.</p>
</td>
</tr>
</table>

<!-- CTA BUTTON -->
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td align="center" style="padding:8px 0 32px;">
<a href=\"""" + JOBS_URL + """\" style="display:inline-block;background:#C8952A;color:#ffffff;font-size:16px;font-weight:700;text-decoration:none;padding:16px 44px;border-radius:8px;">Browse the Job Board</a>
</td></tr></table>

<!-- CV / MATCHING SECTION -->
<table width="100%" cellpadding="0" cellspacing="0" style="background:#FDF6EC;border-left:4px solid #C8952A;border-radius:0 6px 6px 0;margin-bottom:28px;">
<tr><td style="padding:18px 20px;">
<p style="margin:0 0 8px;font-size:14px;font-weight:700;color:#1B2A4A;">A note on direct matching and your CV</p>
<p style="margin:0;font-size:14px;color:#444444;line-height:1.7;">
We actively work to match veterans and military spouses to roles based on their profile and experience. However, some positions require a CV that closely fits the job description and we may not be able to match every profile automatically. based on the standard of their CV. <strong>That is not a reason to hold back.</strong> If you see a role that interests you, review the requirements, update your CV if needed, and go ahead and apply directly. You know your own experience best use the board, explore your options, and take the step.
</p>
</td></tr></table>

<hr style="border:none;border-top:1px solid #EEEEEE;margin:0 0 28px;">

<!-- WHATSAPP SECTION -->
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0FAF4;border:1px solid #C3E6CB;border-radius:8px;margin-bottom:28px;">
<tr><td style="padding:20px 24px;">
<p style="margin:0 0 6px;font-size:15px;font-weight:700;color:#1B2A4A;">Never miss a role join us on WhatsApp</p>
<p style="margin:0 0 14px;font-size:14px;color:#444444;line-height:1.6;">
Our veteran community WhatsApp group gets role updates the moment they go live on the board. Be the first to know. Be the first to apply.
</p>
<a href=\"""" + WHATSAPP_LINK + """\" style="display:inline-block;background:#25D366;color:#ffffff;font-size:14px;font-weight:700;text-decoration:none;padding:11px 24px;border-radius:6px;">Join the Community</a>
</td></tr></table>

<p style="margin:0 0 6px;font-size:14px;color:#555555;line-height:1.7;">
Your military service gave you discipline, resilience, and real-world experience that civilian employers value. VetJobPortal exists to make sure that value is seen and rewarded for veterans and the families who stood beside them. The board is live. Your next opportunity is already there.
</p>

<p style="margin:20px 0 0;font-size:15px;color:#1A1A1A;font-weight:600;">The VetJobPortal Team</p>
</td></tr>

<!-- FOOTER -->
<tr><td style="background:#1B2A4A;border-radius:0 0 10px 10px;padding:24px 40px;text-align:center;">
<p style="margin:0 0 4px;font-size:12px;color:#9AADC4;">VetJobPortal &#8212; Nigeria&#8217;s first dedicated veteran career platform</p>
<p style="margin:0 0 4px;font-size:12px;"><a href="https://vetjobportal.com" style="color:#C8952A;text-decoration:none;">vetjobportal.com</a> &nbsp;&bull;&nbsp; <a href="mailto:support@vetjobportal.com" style="color:#C8952A;text-decoration:none;">support@vetjobportal.com</a></p>
<p style="margin:10px 0 0;font-size:11px;color:#556B88;">You are receiving this because you are a registered member of VetJobPortal.<br>To unsubscribe, reply with the word UNSUBSCRIBE.</p>
</td></tr>

</table></td></tr></table>
</body></html>"""


def build_plain(first_name):
    n = first_name.strip().title() if first_name else "Veteran"
    return (
        "Dear " + n + ",\n\n"
        "The VetJobPortal job board is live, active, and updated daily with real opportunities "
        "for Nigerian veterans and military spouses — on-site roles, remote positions, contracts, "
        "and full-time employment.\n\n"
        "WHAT IS ON THE BOARD:\n"
        "- On-site roles in Nigeria: Active positions with Nigerian organisations and companies, "
        "new listings added daily, open to veterans across all service backgrounds.\n"
        "- Remote roles: Fully remote, international positions for veterans and military spouses — "
        "work from anywhere in Nigeria with a stable internet connection.\n"
        "- Contract roles: Flexible short and medium-term contracts that suit veterans who want "
        "structure without being tied to a single employer.\n"
        "- For military spouses: Remote and flexible roles open to military spouses on the board right now.\n\n"
        "BROWSE THE JOB BOARD:\n" + JOBS_URL + "\n\n"
        "A NOTE ON DIRECT MATCHING AND YOUR CV\n"
        "We work to match veterans and military spouses to roles based on their profile, but some "
        "positions require a CV that closely fits the job description and we may not be able to "
        "match every profile automatically. That is not a reason to hold back. If you see a role "
        "that interests you, update your CV if needed and apply directly. You know your own "
        "experience best.\n\n"
        "JOIN WHATSAPP FOR INSTANT ROLE ALERTS:\n" + WHATSAPP_LINK + "\n"
        "Be the first to know the moment new roles go live on the board.\n\n"
        "Your military service gave you skills and experience that civilian employers value. "
        "VetJobPortal exists to make sure that value is seen and rewarded — for veterans and "
        "the families who stood beside them.\n\n"
        "The VetJobPortal Team\n"
        "vetjobportal.com | support@vetjobportal.com\n\n"
        "You are receiving this as a registered VetJobPortal member. Reply UNSUBSCRIBE to opt out."
    )


def get_smtp():
    c = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
    c.login(SMTP_USER, SMTP_PASSWORD)
    return c


def send_one(to_email, first_name, smtp):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = SUBJECT
        msg["From"]    = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"]      = to_email
        msg["Reply-To"] = FROM_EMAIL
        msg.attach(MIMEText(build_plain(first_name), "plain", "utf-8"))
        msg.attach(MIMEText(build_html(first_name),  "html",  "utf-8"))
        smtp.sendmail(FROM_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"  ERROR {to_email}: {e}")
        return False


def get_users():
    try:
        conn = psycopg2.connect(DB_URL)
        cur  = conn.cursor()
        cur.execute("SELECT email, first_name FROM users WHERE active = TRUE ORDER BY id")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"DB ERROR: {e}")
        sys.exit(1)


def run_test():
    print(f"Sending test to {TEST_EMAIL} ...")
    try:
        smtp = get_smtp()
        ok   = send_one(TEST_EMAIL, "Team", smtp)
        smtp.quit()
        print("SUCCESS - check inbox at support@vetjobportal.com" if ok else "FAILED - check SMTP password")
    except Exception as e:
        print(f"SMTP error: {e}")


def run_bulk():
    users = get_users()
    total = len(users)
    print(f"{total} users found.")
    if input(f"Type YES to send to all {total}: ").strip() != "YES":
        print("Cancelled.")
        return
    smtp   = get_smtp()
    sent   = failed = 0
    for i, (email, fname) in enumerate(users, 1):
        ok      = send_one(email, fname or "", smtp)
        sent   += ok
        failed += (not ok)
        print(f"[{i}/{total}] {'OK' if ok else 'FAIL'} {email}")
        if i % 50 == 0:
            try: smtp.quit()
            except: pass
            smtp = get_smtp()
        time.sleep(DELAY)
    try: smtp.quit()
    except: pass
    print(f"\nDone. Sent: {sent}  Failed: {failed}")


parser = argparse.ArgumentParser()
parser.add_argument("--test", action="store_true")
parser.add_argument("--send", action="store_true")
args = parser.parse_args()
if args.test:   run_test()
elif args.send: run_bulk()
else: print("Usage:\n  python3 send_roles_email.py --test\n  python3 send_roles_email.py --send")
