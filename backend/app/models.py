from datetime import datetime, timezone
from uuid import uuid4
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON
from pgvector.sqlalchemy import Vector

db = SQLAlchemy()

def now():
    return datetime.now(timezone.utc)

def uid():
    return str(uuid4())

class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=uid)
    email = db.Column(db.String(254), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(16), default='user', nullable=False)
    verified = db.Column(db.Boolean, default=False, nullable=False)
    suspended = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)

class Token(db.Model):
    digest = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    purpose = db.Column(db.String(16), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

class Case(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=uid)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, default='')
    language = db.Column(db.String(2), default='fr', nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)

class Document(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=uid)
    case_id = db.Column(db.String(36), db.ForeignKey('case.id', ondelete='CASCADE'), index=True)
    name = db.Column(db.String(255), nullable=False)
    kind = db.Column(db.String(16), nullable=False)  # offer, tender, reference
    key = db.Column(db.String(80), unique=True, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), default='queued', nullable=False)
    error = db.Column(db.String(120))
    page_count = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    chunks = db.Column(JSON, default=list, nullable=False)
    metadata_json = db.Column(JSON, default=dict, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)

class Passage(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    document_id = db.Column(db.String(36), db.ForeignKey('document.id', ondelete='CASCADE'), index=True, nullable=False)
    embedding = db.Column(Vector(256).with_variant(JSON, 'sqlite'), nullable=False)

class Analysis(db.Model):
    __table_args__ = (db.UniqueConstraint('case_id', 'version'),)
    id = db.Column(db.String(36), primary_key=True, default=uid)
    case_id = db.Column(db.String(36), db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='queued', nullable=False)
    progress = db.Column(db.Integer, default=0, nullable=False)
    error = db.Column(db.String(120))
    snapshot = db.Column(JSON, nullable=False)
    report = db.Column(JSON)
    provider_model = db.Column(db.String(150), nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    finished_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now, nullable=False)

class Audit(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=uid)
    actor_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    action = db.Column(db.String(80), nullable=False)
    target_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)

class StorageGarbage(db.Model):
    key = db.Column(db.String(80), primary_key=True)

class ChatMessage(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=uid)
    case_id = db.Column(db.String(36), db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)
    kind = db.Column(db.String(16), default='text', nullable=False)
    content = db.Column(db.Text, default='', nullable=False)
    language = db.Column(db.String(2), default='fr', nullable=False)
    status = db.Column(db.String(16), default='completed', nullable=False)
    error = db.Column(db.String(120))
    analysis_id = db.Column(db.String(36), db.ForeignKey('analysis.id', ondelete='SET NULL'))
    snapshot = db.Column(JSON, default=dict, nullable=False)
    citations = db.Column(JSON, default=list, nullable=False)
    provider_model = db.Column(db.String(150), default='', nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now, nullable=False)
