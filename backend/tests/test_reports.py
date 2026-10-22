from types import SimpleNamespace
import pymupdf
import pytest
from app.models import now
from app.reports import render_pdf


def sample(language):
    arabic = language == 'ar'
    text = 'يجب التحقق من صلاحية الضمان والوثائق الإدارية قبل تقديم العرض.' if arabic else 'Vérifier la validité de la garantie et des pièces administratives avant le dépôt.'
    citation = dict(passage_id='t:0', quote=text, document_name='ملف المناقصة.pdf' if arabic else 'Dossier de consultation.pdf', location='p. 3', kind='tender')
    report = dict(language=language, summary=text, findings=[dict(title='الضمان المالي' if arabic else 'Garantie de soumission', status='a_verifier', severity='high', explanation=text * 4, missing=[text], correction=text, citations=[citation], tender_citation=citation)], limitations=[text], references=[])
    return SimpleNamespace(report=report, snapshot={'title':'وثيقة اختبار - دون قيمة قانونية' if arabic else 'Document de test - sans valeur juridique'}, version=1, created_at=now())


@pytest.mark.parametrize('language',['fr','ar'])
def test_pdf_contains_report_and_renders(app,language,tmp_path):
    content = render_pdf(sample(language))
    assert content.startswith(b'%PDF-')
    with pymupdf.open(stream=content,filetype='pdf') as pdf:
        assert len(pdf)>=1
        assert all(page.get_text().strip() for page in pdf)
        assert pdf[0].get_pixmap().width>500
        assert 'AMANAH' in pdf[0].get_text().replace(' ', '')
