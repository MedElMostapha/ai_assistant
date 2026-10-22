from io import BytesIO
from unittest.mock import patch
from app.models import db, User, Token, Document, Analysis
from app.security import issue_token


def create(client, headers, title='Offre de fournitures'):
    response=client.post('/api/chats',json={'language':'fr'},headers=headers)
    assert response.status_code==201
    return response.json['id']


def test_private_cases_and_admin_cannot_read_offers(client,accounts):
    case=create(client,accounts['first'])
    for role in ['second','admin']:
        assert client.get('/api/cases/'+case,headers=accounts[role]).status_code==404
        assert client.delete('/api/cases/'+case,headers=accounts[role]).status_code==404
    assert client.get('/api/cases/'+case,headers=accounts['first']).status_code==200
    assert client.get('/api/admin/users',headers=accounts['first']).status_code==403
    assert client.get('/api/cases').status_code==401


def test_verification_single_use_and_password_reset_revokes_sessions(client,accounts):
    user=db.session.get(User,'first')
    value=issue_token(user,'verify',1)
    reset=issue_token(user,'reset',1)
    db.session.commit()
    assert client.post('/api/auth/verify',json={'token':value}).status_code==200
    assert client.post('/api/auth/verify',json={'token':value}).status_code==400
    assert client.post('/api/auth/reset',json={'token':reset,'password':'new-password-123'}).status_code==200
    assert client.get('/api/auth/me',headers=accounts['first']).status_code==401
    assert client.post('/api/auth/reset',json={'token':reset,'password':'new-password-123'}).status_code==400


def test_registration_requires_email_confirmation(client):
    with patch('app.routes.mail_token') as mail:
        assert client.post('/api/auth/register',json={'email':'new@example.com','name':'Entreprise','password':'long-password-123'}).status_code==202
        token=mail.call_args.args[1]
    assert client.post('/api/auth/login',json={'email':'new@example.com','password':'long-password-123'}).status_code==403
    assert client.post('/api/auth/verify',json={'token':token}).status_code==200
    assert client.post('/api/auth/login',json={'email':'new@example.com','password':'long-password-123'}).status_code==200


def test_suspension_revokes_sessions(client,accounts):
    assert client.patch('/api/admin/users/first',json={'suspended':True},headers=accounts['admin']).status_code==200
    assert client.get('/api/auth/me',headers=accounts['first']).status_code==401
    assert client.patch('/api/admin/users/admin',json={'suspended':True},headers=accounts['admin']).status_code==400


def test_no_fake_ai_when_unconfigured(client,accounts):
    case=create(client,accounts['first'])
    result=client.post(f'/api/cases/{case}/analyses',headers=accounts['first'])
    assert result.status_code==503
    assert result.json['error']=='ai_not_configured'
    assert db.session.query(Analysis).count()==0


def test_upload_file_spoofing_rejected(client,accounts):
    case=create(client,accounts['first'])
    result=client.post(f'/api/cases/{case}/documents',headers=accounts['first'],data={'kind':'offer','file':(BytesIO(b'not-a-pdf'),'offer.pdf')})
    assert result.status_code==400
    assert db.session.query(Document).count()==0


def test_reports_and_snapshots_are_private(client,accounts):
    case=create(client,accounts['first'])
    item=Analysis(id='private-report',case_id=case,user_id='first',version=1,provider_model='test',snapshot={'passages':[{'id':'p','text':'Texte confidentiel'}]},status='failed')
    db.session.add(item);db.session.commit()
    for role in ['second','admin']:
        assert client.get('/api/analyses/private-report',headers=accounts[role]).status_code==404
        assert client.get('/api/analyses/private-report/passages/p',headers=accounts[role]).status_code==404
        assert client.get('/api/analyses/private-report/pdf',headers=accounts[role]).status_code==404


def test_expired_download_link_rejected(client,app):
    from itsdangerous import URLSafeTimedSerializer
    with patch('itsdangerous.timed.time.time',return_value=1000):
        value=URLSafeTimedSerializer(app.config['SECRET_KEY'],salt='download').dumps({'document':'unknown','user':'first'})
    assert client.get('/api/download/'+value).status_code==404
