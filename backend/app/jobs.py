from celery import Celery
from flask import current_app
from sqlalchemy import select
from .models import db, Document, Passage, Analysis, Case, User, StorageGarbage, ChatMessage, now
from . import storage
from .documents import extract, vector, DocumentError
from .ai import analyze, answer_chat, AnalysisError

celery = Celery('amanah')
celery.conf.update(broker_url=__import__('os').getenv('REDIS_URL', 'redis://localhost:6379/0'), result_backend=None, task_ignore_result=True, task_track_started=False, worker_prefetch_multiplier=1, task_soft_time_limit=3300, task_time_limit=3600)


def dispatch(kind, identifier):
    if current_app.config['TASKS_EAGER']:
        run_job(kind, identifier)
    else:
        execute.delay(kind, identifier)


@celery.task(name='amanah.execute')
def execute(kind, identifier):
    from . import create_app
    app = create_app()
    with app.app_context():
        run_job(kind, identifier)


def run_document(identifier):
    # Atomic state transition makes redelivery harmless.
    claimed = db.session.execute(db.update(Document).where(Document.id == identifier, Document.status == 'queued').values(status='extracting')).rowcount
    db.session.commit()
    if not claimed:
        return
    try:
        doc = db.session.get(Document, identifier)
        data = storage.get(doc.key)
        pages, chunks = extract(doc.name, data, current_app.config['MAX_CASE_PAGES'])
        # Lock the case, so concurrent uploads cannot exceed the aggregate page cap.
        if doc.case_id:
            case = db.session.execute(select(Case).where(Case.id == doc.case_id).with_for_update()).scalar_one_or_none()
            if not case:
                db.session.rollback()
                return
            used = db.session.scalar(select(db.func.coalesce(db.func.sum(Document.page_count), 0)).where(Document.case_id == case.id, Document.id != doc.id))
            if pages + used > current_app.config['MAX_CASE_PAGES']:
                raise DocumentError('page_limit')
        doc = db.session.execute(select(Document).where(Document.id == identifier).with_for_update()).scalar_one_or_none()
        if not doc:
            db.session.rollback()
            return
        db.session.execute(db.delete(Passage).where(Passage.document_id == doc.id))
        for i, chunk in enumerate(chunks):
            chunk['id'] = f'{doc.id}:{i}'
            db.session.add(Passage(id=chunk['id'], document_id=doc.id, embedding=vector(chunk['text'])))
        doc.chunks, doc.page_count, doc.status, doc.error = chunks, pages, 'ready', None
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        doc = db.session.get(Document, identifier)
        if doc:
            doc.status = 'failed'
            doc.error = str(exc) if isinstance(exc, DocumentError) else 'extraction_failed'
            db.session.commit()


def run_analysis(identifier):
    claimed = db.session.execute(db.update(Analysis).where(Analysis.id == identifier, Analysis.status == 'queued').values(status='running', progress=5, attempts=Analysis.attempts + 1)).rowcount
    db.session.commit()
    if not claimed:
        return
    try:
        item = db.session.get(Analysis, identifier)
        user = db.session.get(User, item.user_id)
        if not user or user.suspended:
            raise AnalysisError('account_unavailable')
        if current_app.config['AI_MODEL'] != item.provider_model:
            raise AnalysisError('model_changed')
        snapshot = item.snapshot
        def progress(value):
            result = db.session.execute(db.update(Analysis).where(Analysis.id == identifier, Analysis.status == 'running').values(progress=value))
            db.session.commit()
            if not result.rowcount:
                raise AnalysisError('analysis_cancelled')
        report = analyze(snapshot, progress)
        db.session.execute(db.update(Analysis).where(Analysis.id == identifier, Analysis.status == 'running').values(report=report, status='completed', progress=100, finished_at=now()))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        item = db.session.get(Analysis, identifier)
        if item:
            item.status = 'failed'
            item.error = str(exc) if isinstance(exc, AnalysisError) else 'analysis_failed'
            db.session.commit()


def run_job(kind, identifier):
    if kind == 'document':
        run_document(identifier)
    elif kind == 'analysis':
        run_analysis(identifier)
    elif kind == 'chat':
        run_chat(identifier)
    else:
        raise ValueError('Unknown job type')


def run_chat(identifier):
    claimed = db.session.execute(db.update(ChatMessage).where(ChatMessage.id == identifier, ChatMessage.status == 'queued').values(status='running', attempts=ChatMessage.attempts + 1)).rowcount
    db.session.commit()
    if not claimed:
        return
    try:
        message = db.session.get(ChatMessage, identifier)
        case = db.session.get(Case, message.case_id)
        user = db.session.get(User, case.user_id) if case else None
        if not user or user.suspended:
            raise AnalysisError('account_unavailable')
        if message.provider_model != current_app.config['AI_MODEL']:
            raise AnalysisError('model_changed')
        answer, citations = answer_chat(message.snapshot, message.language)
        db.session.execute(db.update(ChatMessage).where(ChatMessage.id == identifier, ChatMessage.status == 'running').values(content=answer, citations=citations, status='completed'))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        message = db.session.get(ChatMessage, identifier)
        if message:
            message.status = 'failed'
            message.error = str(exc) if isinstance(exc, AnalysisError) else 'analysis_failed'
            db.session.commit()


def collect_garbage():
    for item in db.session.scalars(select(StorageGarbage)).all():
        try:
            storage.delete(item.key)
            db.session.delete(item)
            db.session.commit()
        except Exception:
            db.session.rollback()
