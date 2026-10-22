from datetime import timedelta
from functools import wraps
from hashlib import sha256
import secrets
import smtplib
from email.message import EmailMessage
from flask import abort, current_app, g, request
from .models import db, User, Token, now


def digest(value):
    return sha256(value.encode()).hexdigest()


def issue_token(user, purpose, hours):
    db.session.flush()  # Persist newly registered users before their token FK.
    value = secrets.token_urlsafe(40)
    db.session.add(Token(digest=digest(value), user_id=user.id, purpose=purpose, expires_at=now() + timedelta(hours=hours)))
    return value


def consume_token(value, purpose):
    token = db.session.execute(db.select(Token).where(Token.digest == digest(value), Token.purpose == purpose, Token.expires_at > now()).with_for_update()).scalar_one_or_none()
    if not token:
        abort(400, 'invalid_token')
    user = db.session.get(User, token.user_id)
    db.session.delete(token)
    return user


def auth(admin=False):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            value = request.headers.get('Authorization', '').removeprefix('Bearer ')
            token = db.session.get(Token, digest(value))
            if not token or token.purpose != 'access':
                abort(401, 'unauthorized')
            # Comparison in SQL keeps SQLite tests and PostgreSQL timezone behavior aligned.
            if not db.session.scalar(db.select(Token.digest).where(Token.digest == token.digest, Token.expires_at > now())):
                abort(401, 'unauthorized')
            g.user = db.session.get(User, token.user_id)
            if g.user.suspended or not g.user.verified:
                abort(403, 'account_unavailable')
            if admin and g.user.role != 'admin':
                abort(403, 'admin_required')
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def mail_token(user, value, purpose):
    cfg = current_app.config
    if not cfg['SMTP_HOST']:
        abort(503, 'mail_not_configured')
    url = f"{cfg['FRONTEND_URL']}/?action={purpose}#token={value}"
    message = EmailMessage()
    message['From'], message['To'] = cfg['MAIL_FROM'], user.email
    message['Subject'] = 'Amanah | Confirmation / تأكيد'
    message.set_content(f'Confirmez votre demande / تأكيد طلبك :\n{url}\n\nIgnorez ce message si vous ne l’avez pas demandé.\nتجاهل هذه الرسالة إذا لم تطلبها.')
    try:
        with smtplib.SMTP(cfg['SMTP_HOST'], cfg['SMTP_PORT'], timeout=10) as smtp:
            if cfg['SMTP_TLS']:
                smtp.starttls()
            if cfg['SMTP_USER']:
                smtp.login(cfg['SMTP_USER'], cfg['SMTP_PASSWORD'])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        abort(503, 'mail_unavailable')
