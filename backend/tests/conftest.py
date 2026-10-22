import os
import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from app.models import db, User
from app.security import issue_token

@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': os.getenv('TEST_DATABASE_URL', 'sqlite://'), 'RATELIMIT_STORAGE_URI': 'memory://', 'RATELIMIT_ENABLED': False, 'STORAGE_PATH': str(tmp_path / 'files'), 'STORAGE_BACKEND':'local', 'SECRET_KEY':'test-only-secret', 'TASKS_EAGER': True, 'AI_API_KEY':'', 'AI_MODEL':'test-model', 'SMTP_HOST':'test.invalid'})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def accounts(app):
    results={}
    for role in ['first', 'second', 'admin']:
        user=User(id=role, email=role+'@example.com', name=role, role='admin' if role=='admin' else 'user', verified=True, password_hash=generate_password_hash('test-password-123'))
        db.session.add(user)
        value=issue_token(user,'access',12)
        results[role]={'Authorization':'Bearer '+value}
    db.session.commit()
    return results
