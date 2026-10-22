from io import BytesIO
from unittest.mock import patch
from docx import Document as WordDocument
from app.models import db, Document, Analysis, Case
from app.documents import vector, retrieve
from app.jobs import run_analysis
from app import storage
from test_security import create


def word(text):
    doc=WordDocument();doc.add_paragraph(text);stream=BytesIO();doc.save(stream);return stream.getvalue()


def upload(client,headers,case,kind,text):
    return client.post(f'/api/cases/{case}/documents',headers=headers,data={'kind':kind,'file':(BytesIO(word(text)),kind+'.docx')})


def reference(client,headers,version='v1'):
    return client.post('/api/admin/references',headers=headers,data={'title':'Texte de test - sans valeur juridique','authority':'Autorité fictive','date':'2026-01-01','version':version,'language':'fr','applicability':'Fixture de test uniquement','file':(BytesIO(word('Document de référence fictif pour tester la publication et la lecture.')),'reference.docx')})


def test_word_extraction_delete_and_private_download(client,accounts):
    case=create(client,accounts['first'])
    result=upload(client,accounts['first'],case,'offer','Présentation de notre offre technique et des documents de candidature.')
    assert result.status_code==201
    doc=db.session.get(Document,result.json['document']['id'])
    assert doc.status=='ready'
    assert doc.chunks[0]['location']=='§ 1'
    assert client.get('/api/documents/'+doc.id,headers=accounts['admin']).status_code==404
    link=client.post('/api/documents/'+doc.id+'/download',headers=accounts['first']).json['url']
    assert client.get(link).status_code==200
    key=doc.key
    assert client.delete('/api/cases/'+case,headers=accounts['first']).status_code==204
    assert client.get(link).status_code==404
    assert db.session.query(Document).count()==0
    import pytest
    with pytest.raises(FileNotFoundError):storage.get(key)


def test_reference_requires_review_and_is_immutable_after_publication(client,accounts):
    result=reference(client,accounts['admin'])
    assert result.status_code==201
    identifier=result.json['document']['id']
    assert client.patch('/api/admin/references/'+identifier,headers=accounts['admin'],json={'publication':'published'}).status_code==400
    assert client.patch('/api/admin/references/'+identifier,headers=accounts['admin'],json={'publication':'published','reviewed':True}).status_code==200
    doc=db.session.get(Document,identifier)
    assert client.patch('/api/admin/references/'+identifier,headers=accounts['admin'],json={'publication':'published','reviewed':True,'chunks':doc.chunks}).status_code==409
    assert client.get('/api/admin/references',headers=accounts['first']).status_code==403


def test_snapshot_only_published_sources_and_new_versions(client,accounts,app):
    case=create(client,accounts['first'])
    upload(client,accounts['first'],case,'offer','Notre offre contient les pièces techniques et les éléments administratifs.')
    upload(client,accounts['first'],case,'tender','Le candidat doit fournir une attestation fiscale et une garantie de soumission.')
    published=reference(client,accounts['admin']).json['document']['id']
    draft=reference(client,accounts['admin'],'v2').json['document']['id']
    client.patch('/api/admin/references/'+published,headers=accounts['admin'],json={'publication':'published','reviewed':True})
    app.config['AI_API_KEY']='test-key'
    with patch('app.routes.dispatch'):
        result=client.post(f'/api/cases/{case}/analyses',headers=accounts['first'])
    assert result.status_code==202
    analysis=db.session.get(Analysis,result.json['analysis']['id'])
    assert [r['id'] for r in analysis.snapshot['references']]==[published]
    assert draft not in [p['document_id'] for p in analysis.snapshot['passages']]
    old_snapshot=analysis.snapshot
    assert client.patch('/api/admin/references/'+draft,headers=accounts['admin'],json={'publication':'published','reviewed':True,'replaces':published}).status_code==200
    assert analysis.snapshot==old_snapshot
    analysis.status='failed';db.session.commit()
    with patch('app.routes.dispatch'):
        result=client.post(f'/api/cases/{case}/analyses',headers=accounts['first'])
    assert result.json['analysis']['version']==2
    assert [r['id'] for r in db.session.get(Analysis,result.json['analysis']['id']).snapshot['references']]==[draft]


def test_worker_failure_retry_is_not_a_new_report(client,accounts,app):
    case=create(client,accounts['first'])
    analysis=Analysis(id='job',case_id=case,user_id='first',version=1,provider_model='test-model',snapshot={'title':'test'},status='queued')
    db.session.add(analysis);db.session.commit()
    from app.ai import AnalysisError
    with patch('app.jobs.analyze',side_effect=AnalysisError('ai_unavailable')) as provider:
        run_analysis('job');run_analysis('job')
        assert provider.call_count==1
    assert db.session.get(Analysis,'job').status=='failed'
    app.config['AI_API_KEY']='test'
    report={'summary':'test','findings':[]}
    with patch('app.jobs.analyze',return_value=report):
        result=client.post('/api/analyses/job/retry',headers=accounts['first'])
    assert result.status_code==202
    assert db.session.query(Analysis).count()==1
    assert db.session.get(Analysis,'job').status=='completed'


def test_daily_limit_and_missing_documents(client,accounts,app):
    case=create(client,accounts['first']);app.config['AI_API_KEY']='test'
    assert client.post(f'/api/cases/{case}/analyses',headers=accounts['first']).json['error']=='offer_and_tender_required'
    db.session.add(Analysis(case_id=case,user_id='first',version=1,provider_model='test-model',snapshot={},status='failed'));db.session.commit()
    app.config['DAILY_ANALYSES']=1
    assert client.post(f'/api/cases/{case}/analyses',headers=accounts['first']).status_code==429


def test_arabic_retrieval():
    passages=[{'id':'a','text':'يجب تقديم الضمان المالي مع العرض','embedding':vector('يجب تقديم الضمان المالي مع العرض')},{'id':'b','text':'التوريد خلال ثلاثة أشهر','embedding':vector('التوريد خلال ثلاثة أشهر')}]
    assert retrieve('الضمان المالي',passages,1)[0]['id']=='a'
