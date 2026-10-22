from unittest.mock import patch
import pytest
from app.ai import Citation, Requirement, Requirements, Finding, Findings, Overview, AnalysisError, analyze, validate_citation
from app.documents import vector


def test_invented_citation_rejected():
    with pytest.raises(AnalysisError,match='invalid_citation'):
        validate_citation(Citation(passage_id='missing',quote='Une citation inventée'),{})
    with pytest.raises(AnalysisError,match='invalid_citation'):
        validate_citation(Citation(passage_id='real',quote='Une citation inventée'),{'real':{'text':'Un texte réellement fourni'}})

@pytest.mark.parametrize('status,expected',[('conforme','conforme'),('non_conforme','non_conforme'),('a_verifier','a_verifier')])
def test_grounded_report_and_missing_legal_sources(app,status,expected):
    tender='Le candidat doit fournir une attestation fiscale valide.'
    offer='Notre offre inclut une attestation fiscale valide.'
    passages=[{'id':'t:0','document_id':'t','document_name':'dao.pdf','location':'p. 1','text':tender,'kind':'tender','embedding':vector(tender)},{'id':'o:0','document_id':'o','document_name':'offre.pdf','location':'p. 2','text':offer,'kind':'offer','embedding':vector(offer)}]
    replies=[Requirements(requirements=[Requirement(title='Attestation fiscale',detail=tender,tender_citation=Citation(passage_id='t:0',quote=tender))]),Findings(findings=[Finding(requirement_id='1',status=status,severity='medium',explanation='Constat de test.',missing=['Validité à vérifier'] if status=='a_verifier' else [],correction='Vérifier la date.',citations=[Citation(passage_id='t:0',quote=tender),Citation(passage_id='o:0',quote=offer)])]),Overview(summary='Synthèse de test.',limitations=['Validation professionnelle nécessaire.'])]
    with patch('app.ai.structured',side_effect=replies):
        result=analyze({'language':'fr','passages':passages,'references':[]},lambda p:None)
    assert result['findings'][0]['status']==expected
    assert 'Aucune source juridique' in result['limitations'][-1]
    assert result['findings'][0]['citations'][1]['location']=='p. 2'


def test_scan_without_arabic_ocr_fails_explicitly():
    import pymupdf as fitz
    from app.documents import extract, DocumentError
    pdf=fitz.open();pdf.new_page();data=pdf.tobytes();pdf.close()
    with patch('app.documents.pytesseract.get_languages',return_value=['eng','fra']):
        with pytest.raises(DocumentError,match='ocr_languages_missing'):
            extract('scan.pdf',data,500)


def test_unreadable_scan_is_not_silently_accepted():
    import pymupdf as fitz
    from app.documents import extract, DocumentError
    pdf=fitz.open();pdf.new_page();data=pdf.tobytes();pdf.close()
    with patch('app.documents.pytesseract.get_languages',return_value=['eng','fra','ara']), patch('app.documents.pytesseract.image_to_data',return_value={'text':['illisible'],'conf':['12']}):
        with pytest.raises(DocumentError,match='unreadable_document'):
            extract('scan.pdf',data,500)
