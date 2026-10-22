from flask import render_template_string
from weasyprint import HTML

LABELS = {
    'fr': dict(title='Avis de préparation juridique', summary='Synthèse', requirements='Exigences et conformité', missing='Pièces et informations à vérifier', risks='Risques et corrections', sources='Sources juridiques', limits='Limites de l’analyse', version='Version', advisory='Aide à la préparation de l’offre. Une validation par un professionnel du droit reste nécessaire.', high='Élevé', medium='Modéré', low='Faible', conforme='Conforme', non_conforme='Non conforme', a_verifier='À vérifier', non_applicable='Non applicable', no_sources='Aucune source juridique publiée.', page='Page'),
    'ar': dict(title='رأي للمراجعة القانونية', summary='الخلاصة', requirements='المتطلبات والامتثال', missing='الوثائق والمعلومات المطلوب التحقق منها', risks='المخاطر والتصحيحات', sources='المصادر القانونية', limits='حدود التحليل', version='الإصدار', advisory='مساعدة في إعداد العرض. تظل مراجعة مختص قانوني ضرورية.', high='مرتفع', medium='متوسط', low='منخفض', conforme='مطابق', non_conforme='غير مطابق', a_verifier='للتحقق', non_applicable='غير منطبق', no_sources='لا توجد مصادر قانونية منشورة.', page='صفحة'),
}

TEMPLATE = '''<!doctype html><html lang="{{ r.language }}" dir="{{ 'rtl' if r.language == 'ar' else 'ltr' }}"><head><meta charset="utf-8"><style>
@page { size: A4; margin: 20mm 17mm 23mm; @bottom-center { content: counter(page) " / " counter(pages); direction: ltr; font: 9pt sans-serif; color: #546579; } }
body { font-family: 'Noto Sans', 'Noto Sans Arabic', 'DejaVu Sans', sans-serif; font-size: 10pt; line-height: 1.65; color: #172d45; overflow-wrap: anywhere; }
header { border-bottom: 3px solid #167464; padding-bottom: 12pt; } .brand { letter-spacing: 3px; font-size: 12pt; font-weight: bold; color: #167464; }
h1 { font-size: 24pt; line-height: 1.4; margin: 12pt 0; } h2 { font-size: 15pt; margin-top: 23pt; border-bottom: 1px solid #d8e0e7; padding-bottom: 6pt; } h3 { font-size: 11pt; margin: 6pt 0; }
.card { border: 1px solid #d8e0e7; padding: 10pt; margin: 10pt 0; } .status { font-weight: bold; color: #167464; } blockquote { background: #f2f5f8; margin: 6pt 0; padding: 7pt; font-size: 9pt; } .muted, small { color: #526375; } .advisory { font-size: 9pt; border-{{ 'right' if r.language == 'ar' else 'left' }}: 3px solid #b88933; padding-{{ 'right' if r.language == 'ar' else 'left' }}: 8pt; }
h2, h3 { break-after: avoid; } p { orphans: 3; widows: 3; }
</style></head><body><header><div class="brand">AMANAH · أمانة</div><h1>{{ l.title }}</h1><p>{{ case_title }} · {{ l.version }} {{ version }} · {{ date }}</p></header>
<p class="advisory">{{ l.advisory }}</p><h2>{{ l.summary }}</h2><p>{{ r.summary }}</p>
<h2>{{ l.requirements }}</h2>{% for f in r.findings %}<div class="card"><h3>{{ loop.index }}. {{ f.title }}</h3><div class="status">{{ l[f.status] }} · {{ l[f.severity] }}</div><p>{{ f.explanation }}</p>{% for c in f.sources %}<blockquote><strong>{{ c.document_name }} · {{ c.location }}</strong><br>{{ c.quote }}</blockquote>{% endfor %}</div>{% endfor %}
<h2>{{ l.missing }}</h2><ul>{% for f in r.findings %}{% for item in f.missing %}<li>{{ item }}</li>{% endfor %}{% endfor %}</ul>
<h2>{{ l.risks }}</h2>{% for f in prioritized %}<div class="card"><h3>{{ l[f.severity] }} · {{ f.title }}</h3><p>{{ f.explanation }}</p><p>{{ f.correction }}</p></div>{% endfor %}
<h2>{{ l.sources }}</h2>{% for s in r.references %}<p><strong>{{ s.title }}</strong> · {{ s.authority }} · {{ s.date }} · {{ s.version }}<br>{{ s.applicability }}</p>{% else %}<p>{{ l.no_sources }}</p>{% endfor %}
<h2>{{ l.limits }}</h2><ul>{% for text in r.limitations %}<li>{{ text }}</li>{% endfor %}</ul></body></html>'''


def render_pdf(analysis):
    report = {**analysis.report, 'findings': [dict(f) for f in analysis.report['findings']]}
    for finding in report['findings']:
        seen = set()
        finding['sources'] = []
        for citation in [finding['tender_citation']] + finding['citations']:
            key = (citation['passage_id'], citation['quote'])
            if key not in seen:
                seen.add(key)
                finding['sources'].append(citation)
    content = render_template_string(TEMPLATE, r=report, l=LABELS[report['language']], case_title=analysis.snapshot['title'], version=analysis.version, date=analysis.created_at.strftime('%Y-%m-%d'), prioritized=sorted(report['findings'], key=lambda f: {'high': 0, 'medium': 1, 'low': 2}[f['severity']]))
    def no_network(url, **kwargs):
        raise ValueError('External resources are disabled in reports')
    return HTML(string=content, url_fetcher=no_network).write_pdf()
