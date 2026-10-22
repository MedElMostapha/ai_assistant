"""Conversation-first user workflow. Internal cases never require a user-facing form."""
import json
from flask import Blueprint, abort, current_app, g, jsonify
from sqlalchemy import select, func
from .models import db, Case, Document, Analysis, ChatMessage, User, now
from .security import auth
from .routes import body, field, language, owned_case, ensure_idle, document_json, analysis_json, start_analysis, build_snapshot, queue
from .documents import retrieve

chat_api = Blueprint('chat', __name__)


def message_json(message):
    item = dict(id=message.id, role=message.role, kind=message.kind, content=message.content, language=message.language, status=message.status, error=message.error, citations=message.citations, attempts=message.attempts, created_at=message.created_at.isoformat())
    if message.analysis_id:
        analysis = db.session.get(Analysis, message.analysis_id)
        if analysis:
            item['analysis'] = analysis_json(analysis, True)
    return item


@chat_api.get('/chats')
@auth()
def conversations():
    items = db.session.scalars(select(Case).where(Case.user_id == g.user.id).order_by(Case.created_at.desc())).all()
    return jsonify(chats=[dict(id=c.id, title=c.title, language=c.language) for c in items], ai_configured=bool(current_app.config['AI_API_KEY'] and current_app.config['AI_MODEL']))


@chat_api.post('/chats')
@auth()
def new_conversation():
    lang = language(body())
    item = Case(user_id=g.user.id, title='Nouvelle conversation' if lang == 'fr' else 'محادثة جديدة', language=lang)
    db.session.add(item)
    db.session.commit()
    return jsonify(id=item.id), 201


@chat_api.get('/chats/<identifier>')
@auth()
def conversation(identifier):
    item = owned_case(identifier)
    messages = db.session.scalars(select(ChatMessage).where(ChatMessage.case_id == item.id).order_by(ChatMessage.created_at, ChatMessage.id)).all()
    linked = {m.analysis_id for m in messages if m.analysis_id}
    # Existing dossiers appear as conversations without losing their prior reports.
    legacy = db.session.scalars(select(Analysis).where(Analysis.case_id == item.id).order_by(Analysis.created_at)).all()
    return jsonify(id=item.id, title=item.title, language=item.language, messages=[message_json(m) for m in messages], documents=[document_json(d) for d in db.session.scalars(select(Document).where(Document.case_id == item.id).order_by(Document.created_at))], previous_analyses=[analysis_json(a, True) for a in legacy if a.id not in linked])


@chat_api.post('/chats/<identifier>/messages')
@auth()
def send_message(identifier):
    data = body()
    content = field(data, 'content', 6000)
    lang = language(data)
    intent = data.get('intent', 'message')
    if intent not in ('message', 'analysis'):
        abort(400, 'invalid_intent')
    db.session.execute(select(User).where(User.id == g.user.id).with_for_update()).scalar_one()
    item = owned_case(identifier, True)
    ensure_idle(item.id)
    docs = db.session.scalars(select(Document).where(Document.case_id == item.id)).all()
    configured = bool(current_app.config['AI_API_KEY'] and current_app.config['AI_MODEL'])
    complete = {'offer', 'tender'}.issubset({d.kind for d in docs})
    pending = any(d.status != 'ready' for d in docs)
    prior_analysis = db.session.scalar(select(Analysis.id).where(Analysis.case_id == item.id, Analysis.status == 'completed'))
    # Keep the established daily quota for full opinions. Simple questions have a separate cap.
    if configured and intent == 'message':
        count = db.session.scalar(select(func.count()).select_from(ChatMessage).join(Case, Case.id == ChatMessage.case_id).where(Case.user_id == g.user.id, ChatMessage.role == 'assistant', ChatMessage.kind == 'text', ChatMessage.created_at >= now().replace(hour=0, minute=0, second=0, microsecond=0)))
        if count >= current_app.config.get('DAILY_CHAT_MESSAGES', 30):
            abort(429, 'chat_daily_limit')
    if item.title in ('Nouvelle conversation', 'محادثة جديدة'):
        item.title = content[:80]
    item.language = lang
    db.session.add(ChatMessage(case_id=item.id, role='user', content=content, language=lang))
    # Start the complete opinion from the chat, with no additional form or navigation.
    if complete and not pending and configured and (intent == 'analysis' or not prior_analysis):
        analysis = start_analysis(item.id)
        message = ChatMessage(case_id=item.id, role='assistant', kind='analysis', analysis_id=analysis.id, language=lang)
        db.session.add(message)
        db.session.commit()
        return jsonify(message=message_json(message)), 202
    if intent == 'analysis' or not configured or not docs or pending:
        code = 'attach_documents' if not complete else 'documents_not_ready' if pending else 'ai_not_configured'
        message = ChatMessage(case_id=item.id, role='assistant', kind='notice', content=code, language=lang)
        db.session.add(message)
        db.session.commit()
        return jsonify(message=message_json(message)), 201
    full = build_snapshot(item, docs)
    selected = retrieve(content, [p for p in full['passages'] if p['kind'] != 'reference'], 12) + retrieve(content, [p for p in full['passages'] if p['kind'] == 'reference'], 8)
    history = db.session.scalars(select(ChatMessage).where(ChatMessage.case_id == item.id, ChatMessage.status == 'completed', ChatMessage.kind == 'text').order_by(ChatMessage.created_at.desc()).limit(12)).all()
    latest = db.session.scalar(select(Analysis).where(Analysis.case_id == item.id, Analysis.status == 'completed').order_by(Analysis.version.desc()))
    context = {'passages': selected, 'references': full['references'], 'history': [{'role': m.role, 'content': m.content[:6000]} for m in reversed(history)], 'report_summary': latest.report.get('summary', '') if latest and latest.report else '', 'question': content}
    message = ChatMessage(case_id=item.id, role='assistant', language=lang, status='queued', provider_model=current_app.config['AI_MODEL'], snapshot=context)
    db.session.add(message)
    queue('chat', message)
    return jsonify(message=message_json(message)), 202


@chat_api.get('/chats/<identifier>/messages/<message_id>/passages/<path:passage_id>')
@auth()
def message_passage(identifier, message_id, passage_id):
    owned_case(identifier)
    message = db.session.scalar(select(ChatMessage).where(ChatMessage.id == message_id, ChatMessage.case_id == identifier))
    passage = next((p for p in message.snapshot.get('passages', []) if p['id'] == passage_id), None) if message else None
    if not passage:
        abort(404, 'not_found')
    return jsonify(passage={k: v for k, v in passage.items() if k != 'embedding'})


@chat_api.post('/chats/<identifier>/messages/<message_id>/retry')
@auth()
def retry_message(identifier, message_id):
    db.session.execute(select(User).where(User.id == g.user.id).with_for_update()).scalar_one()
    owned_case(identifier, True)
    ensure_idle(identifier)
    message = db.session.scalar(select(ChatMessage).where(ChatMessage.id == message_id, ChatMessage.case_id == identifier, ChatMessage.role == 'assistant', ChatMessage.kind == 'text'))
    if not message or message.status != 'failed' or message.attempts >= 3:
        abort(409, 'retry_unavailable')
    if not current_app.config['AI_API_KEY'] or current_app.config['AI_MODEL'] != message.provider_model:
        abort(503, 'model_changed')
    message.status, message.error = 'queued', None
    queue('chat', message)
    return jsonify(message=message_json(message)), 202
