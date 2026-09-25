"""
Non-blocking email helper.

Emails in this app are optional notifications (login alerts, onboarding
confirmations, OTPs). They must never block or break the HTTP request that
triggers them. On Render's free plan outbound SMTP ports (25/465/587) are
blocked, so a synchronous smtplib connection hangs until gunicorn kills the
worker, which makes the login/password request itself fail.

send_mail_async() therefore:
  * does nothing (returns False) when SMTP credentials are not configured
  * otherwise sends the message on a background daemon thread
"""

import logging
import threading

from flask import current_app

logger = logging.getLogger(__name__)


def mail_is_configured(app=None) -> bool:
    """Return True only when SMTP username and password are both set."""
    app = app or current_app
    return bool(app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD'))


def _send_in_background(app, msg, description):
    with app.app_context():
        try:
            from app import mail
            mail.send(msg)
            logger.info(f"Email sent: {description}")
        except Exception as e:  # never propagate - email is best-effort
            logger.error(f"Email failed ({description}): {e}")


def send_mail_async(msg, description='email') -> bool:
    """Queue a Flask-Mail Message for background delivery.

    Returns True if the message was queued, False if SMTP is not configured.
    """
    app = current_app._get_current_object()
    if not mail_is_configured(app):
        logger.info(f"SMTP credentials not set - skipped {description}")
        return False

    thread = threading.Thread(
        target=_send_in_background,
        args=(app, msg, description),
        daemon=True,
    )
    thread.start()
    return True
