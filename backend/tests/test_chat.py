from unittest.mock import patch
from app.models import db, Case, ChatMessage, Analysis, Document
from app.jobs import run_chat
from app.ai import AnalysisError, ChatReply, Citation, answer_chat
from test_documents import upload


def new_chat(client, headers, lang='fr'):
    response = client.post('/api/chats', json={'language': lang}, headers=headers)
    assert response.status_code == 201
    return response.json['id']


def test_user_starts_in_chat_without_a_case_form(client, accounts):
    assert client.get('/api/chats', headers=accounts['first']).json['chats'] == []
    assert db.session.query(Case).count() == 0
    assert client.post('/api/cases', json={'title':'Manual case'}, headers=accounts['first']).status_code == 403
    identifier = new_chat(client, accounts['first'])
    response = client.post(f'/api/chats/{identifier}/messages', json={'content':'Comment préparer mon offre ?', 'language':'fr'}, headers=accounts['first'])
    assert response.status_code == 201
    detail = client.get('/api/chats/'+identifier, headers=accounts['first']).json
    assert [m['role'] for m in detail['messages']] == ['user', 'assistant']
    assert detail['messages'][1]['content'] == 'attach_documents'
    assert detail['title'] == 'Comment préparer mon offre ?'


def test_chat_and_its_messages_are_private(client, accounts):
    identifier = new_chat(client, accounts['first'], 'ar')
    client.post(f'/api/chats/{identifier}/messages', json={'content':'كيف أجهز عرضي؟','language':'ar'}, headers=accounts['first'])
    for role in ['second','admin']:
        assert client.get('/api/chats/'+identifier, headers=accounts[role]).status_code == 404
        assert client.post(f'/api/chats/{identifier}/messages', json={'content':'Lire'}, headers=accounts[role]).status_code == 404
        assert client.get('/api/chats', headers=accounts[role]).json['chats'] == []
    assert client.get('/api/chats/'+identifier, headers=accounts['first']).json['messages'][0]['language'] == 'ar'


def with_documents(client, headers):
    identifier = new_chat(client, headers)
    upload(client, headers, identifier, 'offer', 'Notre offre comprend une attestation fiscale valide et une garantie bancaire.')
    upload(client, headers, identifier, 'tender', 'Le candidat doit présenter une attestation fiscale valide et une garantie bancaire.')
    return identifier


def test_analysis_requested_inside_chat_links_existing_pipeline(client, accounts, app):
    identifier = with_documents(client, accounts['first'])
    app.config['AI_API_KEY'] = 'test-key'
    with patch('app.routes.dispatch'):
        response = client.post(f'/api/chats/{identifier}/messages', json={'content':'Analysez mon offre', 'intent':'analysis'}, headers=accounts['first'])
    assert response.status_code == 202
    message = response.json['message']
    assert message['kind'] == 'analysis'
    assert message['analysis']['version'] == 1
    assert db.session.query(Analysis).count() == 1
    assert db.session.query(ChatMessage).count() == 2


def test_follow_up_worker_failure_retry_and_no_duplicate_delivery(client, accounts, app):
    identifier = with_documents(client, accounts['first'])
    app.config['AI_API_KEY'] = 'test-key'
    db.session.add(Analysis(case_id=identifier, user_id='first', version=1, provider_model='test-model', snapshot={}, status='completed', report={'summary':'Avis antérieur de test'}))
    db.session.commit()
    with patch('app.jobs.answer_chat', side_effect=AnalysisError('ai_unavailable')) as provider:
        response = client.post(f'/api/chats/{identifier}/messages', json={'content':'Que dois-je corriger ?'}, headers=accounts['first'])
        message_id = response.json['message']['id']
        assert response.json['message']['status'] == 'failed'
        run_chat(message_id)
        assert provider.call_count == 1
    with patch('app.jobs.answer_chat', return_value=('Réponse de test avec sources.', [])):
        result = client.post(f'/api/chats/{identifier}/messages/{message_id}/retry', headers=accounts['first'])
    assert result.status_code == 202
    assert db.session.get(ChatMessage, message_id).content == 'Réponse de test avec sources.'
    assert db.session.query(ChatMessage).count() == 2
    assert db.session.query(Analysis).count() == 1


def test_chat_refuses_another_send_or_deletion_while_reply_is_running(client, accounts):
    identifier = new_chat(client, accounts['first'])
    db.session.add(ChatMessage(case_id=identifier, role='assistant', status='running'))
    db.session.commit()
    assert client.post(f'/api/chats/{identifier}/messages', json={'content':'Autre question'}, headers=accounts['first']).status_code == 409
    assert client.delete('/api/cases/'+identifier, headers=accounts['first']).status_code == 409


def test_snapshot_citations_remain_private_after_attachment_removed(client, accounts):
    identifier = with_documents(client, accounts['first'])
    doc = db.session.scalar(db.select(Document).where(Document.case_id == identifier, Document.kind == 'offer'))
    passage = {**doc.chunks[0], 'document_id':doc.id, 'document_name':doc.name, 'kind':'offer'}
    message = ChatMessage(case_id=identifier, role='assistant', snapshot={'passages':[passage]})
    db.session.add(message);db.session.commit()
    message_id, doc_id = message.id, doc.id
    path = f'/api/chats/{identifier}/messages/{message_id}/passages/{passage["id"]}'
    assert client.get(path, headers=accounts['second']).status_code == 404
    assert client.delete('/api/documents/'+doc_id, headers=accounts['first']).status_code == 204
    assert client.get(path, headers=accounts['first']).json['passage']['text'] == passage['text']
    assert client.delete('/api/cases/'+identifier, headers=accounts['first']).status_code == 204
    assert db.session.get(ChatMessage, message_id) is None


def test_chat_answer_rejects_invented_or_missing_citations(app):
    import pytest
    snapshot = {'passages':[{'id':'p','text':'Texte réel fourni pour la lecture.'}], 'question':'Question'}
    with patch('app.ai.structured', return_value=ChatReply(answer='Réponse', citations=[])):
        with pytest.raises(AnalysisError, match='invalid_citation'):
            answer_chat(snapshot, 'fr')
    with patch('app.ai.structured', return_value=ChatReply(answer='Réponse', citations=[Citation(passage_id='p',quote='Une source inexistante')])):
        with pytest.raises(AnalysisError, match='invalid_citation'):
            answer_chat(snapshot, 'fr')
