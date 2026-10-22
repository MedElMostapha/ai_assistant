import os
import secrets
from pathlib import Path
from flask import Flask, jsonify, request
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from .models import db

limiter = Limiter(key_func=get_remote_address, default_limits=['300 per minute'])

def create_app(overrides=None):
    app = Flask(__name__)
    # The API is private behind exactly one nginx proxy, which overwrites X-Forwarded-For.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY') or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'postgresql+psycopg://judge:judge@localhost:5432/judge'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={'hide_parameters': True, 'pool_pre_ping': True},
        MAX_CONTENT_LENGTH=26 * 1024 * 1024,
        MAX_FILE_BYTES=int(os.getenv('MAX_FILE_MB', '25')) * 1024 * 1024,
        MAX_CASE_FILES=int(os.getenv('MAX_CASE_FILES', '20')),
        MAX_CASE_PAGES=int(os.getenv('MAX_CASE_PAGES', '500')),
        DAILY_ANALYSES=int(os.getenv('DAILY_ANALYSES', '5')),
        DAILY_CHAT_MESSAGES=int(os.getenv('DAILY_CHAT_MESSAGES', '30')),
        REDIS_URL=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        RATELIMIT_STORAGE_URI=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        STORAGE_BACKEND=os.getenv('STORAGE_BACKEND', 'local'),
        STORAGE_PATH=os.getenv('STORAGE_PATH', str(Path(app.instance_path) / 'files')),
        S3_ENDPOINT=os.getenv('S3_ENDPOINT'), S3_BUCKET=os.getenv('S3_BUCKET', 'judge-private'),
        S3_REGION=os.getenv('S3_REGION', 'us-east-1'),
        S3_ACCESS_KEY=os.getenv('S3_ACCESS_KEY'), S3_SECRET_KEY=os.getenv('S3_SECRET_KEY'),
        AI_API_KEY=os.getenv('AI_API_KEY', ''), AI_BASE_URL=os.getenv('AI_BASE_URL', 'https://api.openai.com/v1'),
        AI_MODEL=os.getenv('AI_MODEL', ''),
        FRONTEND_URL=os.getenv('FRONTEND_URL', 'http://localhost:5173'),
        SMTP_HOST=os.getenv('SMTP_HOST', ''), SMTP_PORT=int(os.getenv('SMTP_PORT', '1025')),
        SMTP_USER=os.getenv('SMTP_USER', ''), SMTP_PASSWORD=os.getenv('SMTP_PASSWORD', ''),
        SMTP_TLS=os.getenv('SMTP_TLS', 'false').lower() == 'true',
        MAIL_FROM=os.getenv('MAIL_FROM', 'avis@localhost'),
        TASKS_EAGER=False, TESTING=False,
    )
    if overrides:
        app.config.update(overrides)
    app.config['MAX_CONTENT_LENGTH'] = app.config['MAX_FILE_BYTES'] + 1024 * 1024
    db.init_app(app)
    Migrate(app, db)
    limiter.init_app(app)
    from .routes import api
    app.register_blueprint(api, url_prefix='/api')
    from .chat import chat_api
    app.register_blueprint(chat_api, url_prefix='/api')
    from .cli import register_cli
    register_cli(app)

    @app.errorhandler(HTTPException)
    def http_error(error):
        code = 'file_too_large' if error.code == 413 else 'too_many_requests' if error.code == 429 and error.description != 'daily_limit' else error.description
        return jsonify(error=code if error.code != 500 else 'server_error'), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        db.session.rollback()
        # Never log SQL parameters, document bodies, provider responses or credentials.
        app.logger.error('Request failed: %s', type(error).__name__)
        return jsonify(error='server_error'), 500

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.get('/api/health')
    def health():
        db.session.execute(db.text('SELECT 1'))
        return jsonify(status='ok', ai_configured=bool(app.config['AI_API_KEY'] and app.config['AI_MODEL']))
    return app
