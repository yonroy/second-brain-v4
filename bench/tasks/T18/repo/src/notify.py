import smtplib
from email.message import EmailMessage


def send_welcome(user):
    msg = EmailMessage()
    msg["To"], msg["Subject"] = user["email"], "Chào mừng"
    msg.set_content(f"Xin chào {user['name']}")
    with smtplib.SMTP("smtp.shop.local") as s:
        s.send_message(msg)
