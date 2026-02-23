#!/usr/bin/env python3
import os
import sys
import smtplib
from email.message import EmailMessage

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body-file", required=True)
    args = parser.parse_args()

    smtp_host = os.environ.get("SMTP_HOST", "smtp-mail.outlook.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not smtp_user or not smtp_pass:
        print("Error: SMTP_USER and SMTP_PASS environment variables are required.")
        sys.exit(1)

    with open(args.body_file, "r", encoding="utf-8") as f:
        body = f.read()

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = args.subject
    msg["From"] = f"Luka AI <{smtp_user}>"
    msg["To"] = args.to

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        print(f"Successfully sent email to {args.to}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
