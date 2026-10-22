from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from uuid import uuid4
import secrets
from flask import Blueprint, abort, current_app, g, jsonify, request, send_file
from sqlalchemy import select, func
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from email_validator import validate_email, EmailNotValidError
from .models import db, User, Token, Case, Document, Passage, Analysis, Audit, StorageGarbage, ChatMessage, now
from .security import auth, issue_token, consume_token, digest, mail_token
from .documents import validate_file, DocumentError, vector
from .jobs import dispatch, collect_garbage
from . import storage, limiter

api = Blueprint('api', __name__)


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, 'invalid_request')
    return data


def field(data, key, limit=180, minimum=1):
    value = data.get(key)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= limit:
        abort(400, 'invalid_' + key)
    return value.strip()


def language(data):
    value = data.get('language', 'fr')
    if value not in ('fr', 'ar'):
        abort(400, 'invalid_language')
    return value


def email(data):
    try:
        return validate_email(field(data, 'email', 254), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        abort(400, 'invalid_email')


def user_json(user):
    return dict(id=user.id, email=user.email, name=user.name, role=user.role, suspended=user.suspended, verified=user.verified)


def document_json(doc, preview=False):
    data = dict(id=doc.id, name=doc.name, kind=doc.kind, status=doc.status, error=doc.error, page_count=doc.page_count, metadata=doc.metadata_json, created_at=doc.created_at.isoformat())
    if preview:
        data['chunks'] = doc.chunks
    return data


def analysis_json(item, full=False):
    data = dict(id=item.id, version=item.version, status=item.status, progress=item.progress, error=item.error, attempts=item.attempts, created_at=item.created_at.isoformat(), model=item.provider_model)
    if full:
        data['report'] = item.report
    return data


def owned_case(identifier, lock=False):
    query = select(Case).where(Case.id == identifier, Case.user_id == g.user.id)
    item = db.session.execute(query.with_for_update() if lock else query).scalar_one_or_none()
    if not item:
        abort(404, 'not_found')
    return item


def owned_analysis(identifier):
    item = db.session.scalar(select(Analysis).where(Analysis.id == identifier, Analysis.user_id == g.user.id))
    if not item:
        abort(404, 'not_found')
    return item


def audit(action, target):
    db.session.add(Audit(actor_id=g.user.id, action=action, target_id=target))


def ensure_idle(case_id):
    if db.session.scalar(select(ChatMessage.id).where(ChatMessage.case_id == case_id, ChatMessage.status.in_(['queued', 'running']))):
        abort(409, 'chat_in_progress')
    if db.session.scalar(select(Analysis.id).where(Analysis.case_id == case_id, Analysis.status.in_(['queued', 'running']))):
        abort(409, 'analysis_in_progress')


def queue(kind, item):
    db.session.commit()  # Worker must see the committed row.
    try:
        dispatch(kind, item.id)
    except Exception:
        db.session.rollback()
        item.status, item.error = 'failed', 'queue_unavailable'
        db.session.commit()
    return item


@api.post('/auth/register')
@limiter.limit('5 per minute')
def register():
    data = body()
    address = email(data)
    name, password = field(data, 'name', 120), field(data, 'password', 256, 12)
    # Generic outcome prevents disclosing which addresses already exist.
    if db.session.scalar(select(User.id).where(User.email == address)):
        return jsonify(message='check_email'), 202
    user = User(id=str(uuid4()), email=address, name=name, password_hash=generate_password_hash(password))
    db.session.add(user)
    value = issue_token(user, 'verify', 24)
    mail_token(user, value, 'verify')
    db.session.commit()
    return jsonify(message='check_email'), 202


@api.post('/auth/verify')
@limiter.limit('10 per minute')
def verify():
    user = consume_token(field(body(), 'token', 200), 'verify')
    user.verified = True
    db.session.commit()
    return jsonify(message='verified')


@api.post('/auth/login')
@limiter.limit('10 per minute')
def login():
    data = body()
    address, password = email(data), field(data, 'password', 256)
    user = db.session.scalar(select(User).where(User.email == address))
    # Always compute a password hash check, including for unknown accounts.
    stored = user.password_hash if user else generate_password_hash('unavailable-password')
    if not check_password_hash(stored, password) or not user:
        abort(401, 'invalid_credentials')
    if not user.verified or user.suspended:
        abort(403, 'account_unavailable')
    value = issue_token(user, 'access', 12)
    db.session.commit()
    return jsonify(token=value, user=user_json(user))


@api.post('/auth/forgot')
@limiter.limit('3 per minute')
def forgot():
    address = email(body())
    user = db.session.scalar(select(User).where(User.email == address))
    if user and not user.suspended:
        # Existing reset links become invalid when a fresh one is requested.
        db.session.execute(db.delete(Token).where(Token.user_id == user.id, Token.purpose == 'reset'))
        value = issue_token(user, 'reset', 1)
        mail_token(user, value, 'reset')
        db.session.commit()
    return jsonify(message='check_email'), 202


@api.post('/auth/resend')
@limiter.limit('3 per minute')
def resend():
    user = db.session.scalar(select(User).where(User.email == email(body()), User.verified.is_(False)))
    if user:
        db.session.execute(db.delete(Token).where(Token.user_id == user.id, Token.purpose == 'verify'))
        value = issue_token(user, 'verify', 24)
        mail_token(user, value, 'verify')
        db.session.commit()
    return jsonify(message='check_email'), 202


@api.post('/auth/reset')
@limiter.limit('5 per minute')
def reset():
    data = body()
    password = field(data, 'password', 256, 12)
    user = consume_token(field(data, 'token', 200), 'reset')
    user.password_hash = generate_password_hash(password)
    db.session.execute(db.delete(Token).where(Token.user_id == user.id, Token.purpose.in_(['access', 'reset'])))
    db.session.commit()
    return jsonify(message='password_updated')


@api.get('/auth/me')
@auth()
def me():
    return jsonify(user=user_json(g.user))


@api.post('/auth/logout')
@auth()
def logout():
    db.session.execute(db.delete(Token).where(Token.digest == digest(request.headers['Authorization'].removeprefix('Bearer '))))
    db.session.commit()
    return '', 204


@api.get('/cases')
@auth()
def cases():
    items = db.session.scalars(select(Case).where(Case.user_id == g.user.id).order_by(Case.created_at.desc())).all()
    results = []
    for item in items:
        analyses = db.session.scalars(select(Analysis).where(Analysis.case_id == item.id).order_by(Analysis.version.desc())).all()
        results.append(dict(id=item.id, title=item.title, description=item.description, language=item.language, created_at=item.created_at.isoformat(), document_count=db.session.scalar(select(func.count()).select_from(Document).where(Document.case_id == item.id)), latest_analysis=analysis_json(analyses[0]) if analyses else None))
    count = db.session.scalar(select(func.count()).select_from(Analysis).where(Analysis.user_id == g.user.id, Analysis.created_at >= now().replace(hour=0, minute=0, second=0, microsecond=0)))
    return jsonify(cases=results, usage=dict(today=count, limit=current_app.config['DAILY_ANALYSES']), ai_configured=bool(current_app.config['AI_API_KEY'] and current_app.config['AI_MODEL']))


@api.post('/cases')
@auth(admin=True)
def create_case():
    data = body()
    item = Case(user_id=g.user.id, title=field(data, 'title'), description=field(data, 'description', 3000, 0) if 'description' in data else '', language=language(data))
    db.session.add(item)
    db.session.commit()
    return jsonify(id=item.id), 201


@api.get('/cases/<identifier>')
@auth()
def case_detail(identifier):
    item = owned_case(identifier)
    documents = db.session.scalars(select(Document).where(Document.case_id == item.id).order_by(Document.created_at)).all()
    analyses = db.session.scalars(select(Analysis).where(Analysis.case_id == item.id).order_by(Analysis.version.desc())).all()
    return jsonify(id=item.id, title=item.title, description=item.description, language=item.language, documents=[document_json(d) for d in documents], analyses=[analysis_json(a) for a in analyses])


@api.delete('/cases/<identifier>')
@auth()
def delete_case(identifier):
    item = owned_case(identifier, True)
    ensure_idle(item.id)
    docs = db.session.scalars(select(Document).where(Document.case_id == item.id)).all()
    for doc in docs:
        db.session.add(StorageGarbage(key=doc.key))
        db.session.execute(db.delete(Passage).where(Passage.document_id == doc.id))
        db.session.delete(doc)
    db.session.execute(db.delete(ChatMessage).where(ChatMessage.case_id == item.id))
    db.session.execute(db.delete(Analysis).where(Analysis.case_id == item.id))
    db.session.delete(item)
    db.session.commit()
    collect_garbage()
    return '', 204


def upload_document(case=None):
    file = request.files.get('file')
    if not file or not file.filename or len(file.filename) > 255:
        abort(400, 'invalid_file')
    data = file.read(current_app.config['MAX_FILE_BYTES'] + 1)
    if len(data) > current_app.config['MAX_FILE_BYTES']:
        abort(413, 'file_too_large')
    try:
        validate_file(file.filename, data)
    except DocumentError as exc:
        abort(400, str(exc))
    kind = request.form.get('kind') if case else 'reference'
    if kind not in ('offer', 'tender', 'reference') or (case and kind == 'reference'):
        abort(400, 'invalid_kind')
    metadata = {}
    if not case:
        metadata = dict(title=field(request.form, 'title'), authority=field(request.form, 'authority'), date=field(request.form, 'date', 10), version=field(request.form, 'version', 60), language=language(request.form), applicability=field(request.form, 'applicability', 1000), publication='draft')
        try:
            datetime.strptime(metadata['date'], '%Y-%m-%d')
        except ValueError:
            abort(400, 'invalid_date')
    if case:
        count = db.session.scalar(select(func.count()).select_from(Document).where(Document.case_id == case.id))
        if count >= current_app.config['MAX_CASE_FILES']:
            abort(400, 'file_limit')
    item = Document(id=str(uuid4()), case_id=case.id if case else None, name=file.filename.replace('/', '_').replace('\\', '_'), kind=kind, key=secrets.token_hex(32), sha256=sha256(data).hexdigest(), metadata_json=metadata)
    try:
        storage.put(item.key, data)
        db.session.add(item)
        if not case:
            audit('reference.upload', item.id)
        queue('document', item)
    except Exception:
        db.session.rollback()
        try:
            storage.delete(item.key)
        except Exception:
            pass
        abort(503, 'storage_unavailable')
    return jsonify(document=document_json(item)), 201


@api.post('/cases/<identifier>/documents')
@auth()
def upload_case_document(identifier):
    item = owned_case(identifier, True)
    ensure_idle(item.id)
    return upload_document(item)


@api.get('/documents/<identifier>')
@auth()
def document_detail(identifier):
    item = db.session.get(Document, identifier)
    if not item:
        abort(404, 'not_found')
    if item.case_id:
        owned_case(item.case_id)
    elif g.user.role != 'admin':
        abort(404, 'not_found')
    return jsonify(document=document_json(item, True))


@api.post('/documents/<identifier>/download')
@auth()
def download_link(identifier):
    document_detail(identifier)  # Applies owner/reference permissions.
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='download')
    value = serializer.dumps({'document': identifier, 'user': g.user.id})
    return jsonify(url=f'/api/download/{value}', expires_in=120)


@api.get('/download/<value>')
def download(value):
    try:
        data = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='download').loads(value, max_age=120)
    except (BadSignature, SignatureExpired):
        abort(404, 'not_found')
    user = db.session.get(User, data['user'])
    doc = db.session.get(Document, data['document'])
    if not user or user.suspended or not user.verified or not doc:
        abort(404, 'not_found')
    if doc.case_id:
        item = db.session.get(Case, doc.case_id)
        if not item or item.user_id != user.id:
            abort(404, 'not_found')
    elif user.role != 'admin':
        abort(404, 'not_found')
    try:
        content = storage.get(doc.key)
    except Exception:
        abort(503, 'storage_unavailable')
    return send_file(BytesIO(content), download_name=doc.name, as_attachment=True, mimetype='application/octet-stream')


@api.delete('/documents/<identifier>')
@auth()
def delete_document(identifier):
    doc = db.session.get(Document, identifier)
    if not doc or not doc.case_id:
        abort(404, 'not_found')
    owned_case(doc.case_id, True)
    ensure_idle(doc.case_id)
    db.session.add(StorageGarbage(key=doc.key))
    db.session.execute(db.delete(Passage).where(Passage.document_id == doc.id))
    db.session.delete(doc)
    db.session.commit()
    collect_garbage()
    return '', 204


@api.post('/documents/<identifier>/retry')
@auth()
def retry_document(identifier):
    doc = db.session.get(Document, identifier)
    if not doc:
        abort(404, 'not_found')
    if doc.case_id:
        owned_case(doc.case_id, True)
        ensure_idle(doc.case_id)
    elif g.user.role != 'admin':
        abort(404, 'not_found')
    if doc.status != 'failed':
        abort(409, 'not_failed')
    doc.status, doc.error = 'queued', None
    queue('document', doc)
    return jsonify(document=document_json(doc)), 202


def build_snapshot(item, docs):
    references = db.session.scalars(select(Document).where(Document.kind == 'reference', Document.status == 'ready')).all()
    references = [r for r in references if r.metadata_json.get('publication') == 'published']
    passages = []
    for doc in docs + references:
        for chunk in doc.chunks:
            passages.append({**chunk, 'document_id': doc.id, 'document_name': doc.name, 'kind': doc.kind, 'embedding': vector(chunk['text'])})
    return {'language': item.language, 'title': item.title, 'documents': [{'id': d.id, 'sha256': d.sha256, 'name': d.name} for d in docs], 'references': [{'id': r.id, 'name': r.name, 'sha256': r.sha256, **r.metadata_json} for r in references], 'passages': passages}


def lock_quota():
    # Serialize new analyses/retries for this user, across all their cases.
    db.session.execute(select(User).where(User.id == g.user.id).with_for_update()).scalar_one()
    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.session.scalar(select(func.count()).select_from(Analysis).where(Analysis.user_id == g.user.id, Analysis.created_at >= today))
    if count >= current_app.config['DAILY_ANALYSES']:
        abort(429, 'daily_limit')


def start_analysis(identifier):
    if not current_app.config['AI_API_KEY'] or not current_app.config['AI_MODEL']:
        abort(503, 'ai_not_configured')
    lock_quota()
    item = owned_case(identifier, True)
    ensure_idle(item.id)
    docs = db.session.scalars(select(Document).where(Document.case_id == item.id)).all()
    if not {'offer', 'tender'}.issubset({d.kind for d in docs}):
        abort(400, 'offer_and_tender_required')
    if any(d.status != 'ready' for d in docs):
        abort(400, 'documents_not_ready')
    version = db.session.scalar(select(func.coalesce(func.max(Analysis.version), 0)).where(Analysis.case_id == item.id)) + 1
    analysis = Analysis(case_id=item.id, user_id=g.user.id, version=version, provider_model=current_app.config['AI_MODEL'], snapshot=build_snapshot(item, docs))
    db.session.add(analysis)
    queue('analysis', analysis)
    return analysis


@api.post('/cases/<identifier>/analyses')
@auth()
def create_analysis(identifier):
    return jsonify(analysis=analysis_json(start_analysis(identifier))), 202


@api.get('/analyses/<identifier>')
@auth()
def get_analysis(identifier):
    return jsonify(analysis=analysis_json(owned_analysis(identifier), True))


@api.get('/analyses/<identifier>/passages/<path:passage_id>')
@auth()
def get_passage(identifier, passage_id):
    item = owned_analysis(identifier)
    passage = next((p for p in item.snapshot['passages'] if p['id'] == passage_id), None)
    if not passage:
        abort(404, 'not_found')
    return jsonify(passage={k: v for k, v in passage.items() if k != 'embedding'})


@api.post('/analyses/<identifier>/retry')
@auth()
def retry_analysis(identifier):
    db.session.execute(select(User).where(User.id == g.user.id).with_for_update()).scalar_one()
    item = owned_analysis(identifier)
    owned_case(item.case_id, True)
    ensure_idle(item.case_id)
    if item.status != 'failed' or item.attempts >= 3:
        abort(409, 'retry_unavailable')
    if not current_app.config['AI_API_KEY'] or current_app.config['AI_MODEL'] != item.provider_model:
        abort(503, 'model_changed')
    item.status, item.error, item.progress = 'queued', None, 0
    queue('analysis', item)
    return jsonify(analysis=analysis_json(item)), 202


@api.get('/analyses/<identifier>/pdf')
@auth()
def pdf(identifier):
    from .reports import render_pdf
    item = owned_analysis(identifier)
    if item.status != 'completed':
        abort(409, 'report_not_ready')
    return send_file(BytesIO(render_pdf(item)), mimetype='application/pdf', as_attachment=True, download_name=f'avis-v{item.version}.pdf')


@api.get('/admin/references')
@auth(admin=True)
def references():
    items = db.session.scalars(select(Document).where(Document.kind == 'reference').order_by(Document.created_at.desc())).all()
    return jsonify(documents=[document_json(d) for d in items])


@api.post('/admin/references')
@auth(admin=True)
def upload_reference():
    return upload_document()


@api.patch('/admin/references/<identifier>')
@auth(admin=True)
def update_reference(identifier):
    doc = db.session.execute(select(Document).where(Document.id == identifier, Document.kind == 'reference').with_for_update()).scalar_one_or_none()
    if not doc:
        abort(404, 'not_found')
    data = body()
    publication = data.get('publication')
    if publication not in ('published', 'archived', 'draft'):
        abort(400, 'invalid_publication')
    previous = doc.metadata_json.get('publication')
    # Published/archived content is immutable: upload a replacement version instead.
    if 'chunks' in data:
        if previous != 'draft' or doc.status != 'ready':
            abort(409, 'immutable_reference')
        chunks = data['chunks']
        if not isinstance(chunks, list) or len(chunks) != len(doc.chunks):
            abort(400, 'invalid_chunks')
        edited = []
        for original, value in zip(doc.chunks, chunks):
            if not isinstance(value, dict):
                abort(400, 'invalid_chunks')
            edited.append({**original, 'text': field(value, 'text', 5000)})
        doc.chunks = edited
        db.session.execute(db.delete(Passage).where(Passage.document_id == doc.id))
        for chunk in edited:
            db.session.add(Passage(id=chunk['id'], document_id=doc.id, embedding=vector(chunk['text'])))
    if publication == 'published':
        if doc.status != 'ready' or not doc.chunks or data.get('reviewed') is not True:
            abort(400, 'review_required')
        # Atomically archive an explicitly selected predecessor.
        replaces = data.get('replaces')
        if replaces:
            old = db.session.get(Document, replaces)
            if not old or old.kind != 'reference' or old.id == doc.id:
                abort(400, 'invalid_replacement')
            old.metadata_json = {**old.metadata_json, 'publication': 'archived'}
            audit('reference.replace', old.id)
    if previous in ('published', 'archived') and publication == 'draft':
        abort(409, 'immutable_reference')
    doc.metadata_json = {**doc.metadata_json, 'publication': publication}
    audit('reference.' + publication, doc.id)
    db.session.commit()
    return jsonify(document=document_json(doc))


@api.get('/admin/users')
@auth(admin=True)
def users():
    results = []
    for user in db.session.scalars(select(User).order_by(User.created_at.desc())).all():
        count = db.session.scalar(select(func.count()).select_from(Analysis).where(Analysis.user_id == user.id))
        results.append({**user_json(user), 'analysis_count': count})
    return jsonify(users=results)


@api.patch('/admin/users/<identifier>')
@auth(admin=True)
def suspend(identifier):
    user = db.session.get(User, identifier)
    data = body()
    if not user:
        abort(404, 'not_found')
    if user.role == 'admin' or not isinstance(data.get('suspended'), bool):
        abort(400, 'invalid_suspension')
    user.suspended = data['suspended']
    if user.suspended:
        db.session.execute(db.delete(Token).where(Token.user_id == user.id))
    audit('user.suspend' if user.suspended else 'user.activate', user.id)
    db.session.commit()
    return jsonify(user=user_json(user))


@api.get('/admin/jobs')
@auth(admin=True)
def jobs():
    analyses = db.session.scalars(select(Analysis).where(Analysis.status.in_(['queued', 'running', 'failed'])).order_by(Analysis.created_at.desc()).limit(100)).all()
    docs = db.session.scalars(select(Document).where(Document.status.in_(['queued', 'extracting', 'failed'])).order_by(Document.created_at.desc()).limit(100)).all()
    chats = db.session.scalars(select(ChatMessage).where(ChatMessage.role == 'assistant', ChatMessage.status.in_(['queued', 'running', 'failed'])).order_by(ChatMessage.created_at.desc()).limit(100)).all()
    # Only operational metadata; administrators cannot read other users' offers.
    return jsonify(jobs=[dict(id=a.id, type='analysis', status=a.status, error=a.error, attempts=a.attempts) for a in analyses] + [dict(id=d.id, type='document', status=d.status, error=d.error) for d in docs] + [dict(id=m.id, type='chat', status=m.status, error=m.error, attempts=m.attempts) for m in chats])


@api.post('/admin/jobs/<kind>/<identifier>/retry')
@auth(admin=True)
def admin_retry(kind, identifier):
    model = Analysis if kind == 'analysis' else Document if kind == 'document' else ChatMessage if kind == 'chat' else None
    if not model:
        abort(404, 'not_found')
    item = db.session.get(model, identifier)
    if not item:
        abort(404, 'not_found')
    if kind in ('analysis', 'chat'):
        owner_id = item.user_id if kind == 'analysis' else db.session.get(Case, item.case_id).user_id
        db.session.execute(select(User).where(User.id == owner_id).with_for_update()).scalar_one()
    if item.case_id:
        db.session.execute(select(Case).where(Case.id == item.case_id).with_for_update()).scalar_one()
        ensure_idle(item.case_id)
    db.session.refresh(item, with_for_update=True)
    if item.status != 'failed':
        abort(409, 'not_failed')
    if kind in ('analysis', 'chat') and item.attempts >= 3:
        abort(409, 'retry_unavailable')
    if kind in ('analysis', 'chat') and (not current_app.config['AI_API_KEY'] or current_app.config['AI_MODEL'] != item.provider_model):
        abort(503, 'model_changed')
    item.status, item.error = 'queued', None
    audit('job.retry', item.id)
    queue(kind, item)
    return jsonify(status=item.status), 202
