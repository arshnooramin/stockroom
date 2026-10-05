import smtplib
import ssl
from email.message import EmailMessage

import requests
from flask import current_app, url_for

from stockroom.extensions import db
from stockroom.models import Order, Role, User


def send_email(to: list[str], subject: str, body: str) -> None:
    """Send a plain-text email. Failures are logged, never raised, so they can't break a request."""
    cfg = current_app.config
    to = sorted(set(to))
    if not to:
        return
    subject = f"[{cfg['APP_NAME']}] {subject}"

    try:
        if cfg["RESEND_API_KEY"]:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {cfg['RESEND_API_KEY']}"},
                json={"from": cfg["MAIL_FROM"], "to": to, "subject": subject, "text": body},
                timeout=10,
            )
            resp.raise_for_status()
        elif cfg["MAIL_SERVER"]:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = cfg["MAIL_FROM"]
            msg["To"] = ", ".join(to)
            msg.set_content(body)
            with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as smtp:
                if cfg["MAIL_USE_TLS"]:
                    smtp.starttls(context=ssl.create_default_context())
                if cfg["MAIL_USERNAME"]:
                    smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
                smtp.send_message(msg)
        else:
            current_app.logger.info(
                "Email not configured; would send to %s: %s\n%s", to, subject, body
            )
    except (requests.RequestException, smtplib.SMTPException, OSError):
        current_app.logger.exception("Failed to send email to %s", to)


def notify_new_order(order: Order) -> None:
    admins = db.session.scalars(db.select(User.email).filter_by(role=Role.ADMIN)).all()
    creator = order.created_by
    send_email(
        admins,
        f"New order #{order.id} from {order.project.name}",
        f"{creator.name if creator else 'Someone'} ({creator.email if creator else 'unknown'}) "
        f"placed order #{order.id} with {order.vendor} for project {order.project.name}.\n\n"
        f"Total: ${order.total:,.2f}\n\n"
        f"Review it here: {url_for('orders.edit', order_id=order.id, _external=True)}\n",
    )


def notify_status_change(order: Order) -> None:
    send_email(
        [m.email for m in order.project.members],
        f"Order #{order.id} is now {order.status.value.lower()}",
        f"Order #{order.id} with {order.vendor} for project {order.project.name} "
        f"was marked {order.status.value.lower()}.\n\n"
        f"View it here: {url_for('projects.show', project_id=order.project_id, _external=True)}\n",
    )
