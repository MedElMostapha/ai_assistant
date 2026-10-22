from io import BytesIO
from hashlib import sha256
import math
import re
import unicodedata
from zipfile import ZipFile, BadZipFile
import pymupdf as fitz
from docx import Document as WordDocument
from PIL import Image
import pytesseract


class DocumentError(ValueError):
    pass


def validate_file(name, data):
    suffix = name.lower().rsplit('.', 1)[-1]
    if suffix == 'pdf' and data.startswith(b'%PDF-'):
        return
    if suffix == 'docx' and data.startswith(b'PK'):
        try:
            with ZipFile(BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > 2000 or sum(i.file_size for i in infos) > 80 * 1024 * 1024:
                    raise DocumentError('unsafe_archive')
                if 'word/document.xml' not in archive.namelist():
                    raise DocumentError('invalid_file')
                # Embedded files and macros are not needed to read procurement documents.
                if any('vbaProject' in i.filename or '/embeddings/' in i.filename for i in infos):
                    raise DocumentError('unsafe_archive')
            return
        except BadZipFile:
            pass
    raise DocumentError('invalid_file')


def extract(name, data, page_limit):
    validate_file(name, data)
    sections = []
    if name.lower().endswith('.pdf'):
        try:
            with fitz.open(stream=data, filetype='pdf') as pdf:
                if pdf.needs_pass:
                    raise DocumentError('encrypted_pdf')
                if not 0 < len(pdf) <= page_limit:
                    raise DocumentError('page_limit')
                languages = set(pytesseract.get_languages(config=''))
                for i, page in enumerate(pdf):
                    text = page.get_text().strip()
                    # Image-dominant pages may contain only a selectable page header.
                    images = page.get_image_info()
                    image_area = sum(fitz.Rect(item['bbox']).get_area() for item in images)
                    if len(text) < 60 or image_area > page.rect.get_area() * .6:
                        if not {'fra', 'ara'}.issubset(languages):
                            raise DocumentError('ocr_languages_missing')
                        scale = min(2, 3000 / max(page.rect.width, page.rect.height, 1))
                        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                        image = Image.open(BytesIO(pix.tobytes('png')))
                        result = pytesseract.image_to_data(image, lang='fra+ara', timeout=90, output_type=pytesseract.Output.DICT)
                        words = [(word, float(conf)) for word, conf in zip(result['text'], result['conf']) if word.strip() and float(conf) >= 0]
                        if not words or sum(conf for _, conf in words) / len(words) < 45:
                            raise DocumentError('unreadable_document')
                        text = ' '.join(word for word, _ in words)
                    if len(text.strip()) < 15 or '\ufffd' in text:
                        raise DocumentError('unreadable_document')
                    sections.append((f'p. {i + 1}', text))
                pages = len(pdf)
        except DocumentError:
            raise
        except Exception as exc:
            raise DocumentError('extraction_failed') from exc
    else:
        try:
            doc = WordDocument(BytesIO(data))
            # iter_inner_content retains table/paragraph order.
            for i, block in enumerate(doc.iter_inner_content(), 1):
                text = block.text if hasattr(block, 'text') else '\n'.join(' | '.join(c.text for c in row.cells) for row in block.rows)
                if text.strip():
                    sections.append((f'§ {i}', text.strip()))
            chars = sum(len(text) for _, text in sections)
            pages = max(1, math.ceil(chars / 2500))  # DOCX has no reliable physical pages.
            if pages > page_limit:
                raise DocumentError('page_limit')
        except DocumentError:
            raise
        except Exception as exc:
            raise DocumentError('extraction_failed') from exc
    if not sections or sum(len(text) for _, text in sections) < 40:
        raise DocumentError('unreadable_document')
    if sum(len(text) for _, text in sections) > 2_000_000:
        raise DocumentError('text_limit')
    chunks = []
    for location, text in sections:
        for offset in range(0, len(text), 1800):
            chunks.append({'location': location, 'text': text[offset:offset + 2000]})
    return pages, chunks


def normalize(text):
    value = unicodedata.normalize('NFKD', text.lower())
    return ''.join(c for c in value if not unicodedata.combining(c))


def vector(text):
    """Local multilingual feature hashing. No document text leaves the worker here."""
    values = [0.] * 256
    words = re.findall(r'\w+', normalize(text))
    for word in words:
        features = [word] + [word[i:i + 3] for i in range(max(0, len(word) - 2))]
        for feature in features:
            digest = sha256(feature.encode()).digest()
            values[int.from_bytes(digest[:2], 'big') % 256] += 1 if digest[2] & 1 else -1
    norm = math.sqrt(sum(v * v for v in values)) or 1
    return [v / norm for v in values]


def retrieve(query, passages, limit=6):
    q = vector(query)
    ranked = sorted(passages, key=lambda p: sum(a * b for a, b in zip(q, p['embedding'])), reverse=True)
    return ranked[:limit]
