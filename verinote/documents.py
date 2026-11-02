"""Bounded document decoding; originals are stored separately, unchanged."""
import io
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib
from html.parser import HTMLParser
from pathlib import Path

MAX_BYTES = 32 * 1024 * 1024
MAX_TEXT = 128_000
MAX_DOCX_XML_BYTES = 16 * 1024 * 1024
MAX_URL_FETCH_BYTES = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# [STUDY-CUSTOM] Obsidian / Markdown 볼트 ZIP 가져오기(Import) 파서
# ---------------------------------------------------------------------------
def _extract_zip_vault_text(raw: bytes) -> str:
    """Extract and merge markdown files from an Obsidian vault zip archive."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        notes = []
        total_size = 0
        for name in sorted(archive.namelist()):
            # 시스템/설정 폴더(.obsidian, __MACOSX 등) 및 디렉토리 제외
            if name.endswith('/') or '/.' in name or name.startswith(('.', '__MACOSX')):
                continue
            lower = name.lower()
            if not (lower.endswith('.md') or lower.endswith('.markdown') or lower.endswith('.txt')):
                continue

            info = archive.getinfo(name)
            total_size += info.file_size
            if total_size > MAX_DOCX_XML_BYTES:
                raise ValueError('ZIP 볼트 압축 해제 크기가 16 MiB를 초과합니다.')

            try:
                content = archive.read(name).decode('utf-8-sig', errors='replace').strip()
            except Exception as exc:
                continue

            if content:
                note_name = Path(name).name
                notes.append(f'--- [노트: {note_name}] ---\n{content}')

        if not notes:
            raise ValueError('ZIP 아카이브 내에 읽을 수 있는 마크다운(.md) 파일이 없습니다.')

        merged = '\n\n'.join(notes)
        if len(merged) > MAX_TEXT:
            # 상한선에 맞게 조정 안내
            raise ValueError('추출 본문은 128,000자까지 분석할 수 있습니다. 볼트 범위를 나누어 등록하세요.')
        return merged


# ---------------------------------------------------------------------------
# [STUDY-CUSTOM] PPTX(파워포인트) 슬라이드 문서 텍스트 파서
# ---------------------------------------------------------------------------
def _extract_pptx_text(raw: bytes) -> str:
    """Extract ordered text from slide*.xml in a PPTX archive."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        slide_names = [name for name in archive.namelist() if re.match(r'^ppt/slides/slide\d+\.xml$', name)]
        if not slide_names:
            raise ValueError('PPTX 슬라이드를 찾을 수 없습니다.')
        slide_names.sort(key=lambda x: int(re.search(r'\d+', x).group()))

        total_xml_size = sum(archive.getinfo(name).file_size for name in slide_names)
        if total_xml_size > MAX_DOCX_XML_BYTES:
            raise ValueError('PPTX 슬라이드 XML은 압축 해제 후 16 MiB까지 지원합니다. 문서를 나누어 등록하세요.')

        ns_a = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
        slides_text = []

        for idx, name in enumerate(slide_names, 1):
            info = archive.getinfo(name)
            try:
                with archive.open(info) as src:
                    xml_data = src.read(MAX_DOCX_XML_BYTES + 1)
            except (RuntimeError, EOFError, zlib.error) as exc:
                raise ValueError('PPTX 슬라이드를 읽을 수 없습니다. 파일 손상을 확인하세요.') from exc

            if len(xml_data) > MAX_DOCX_XML_BYTES:
                raise ValueError('PPTX 슬라이드 크기 제한을 초과했습니다.')
            if b'<!DOCTYPE' in xml_data or b'<!ENTITY' in xml_data:
                raise ValueError('PPTX XML 엔티티는 허용하지 않습니다.')

            root = ET.fromstring(xml_data)
            paragraphs = []
            for p in root.iter(ns_a + 'p'):
                line = ''.join((node.text or '') for node in p.iter(ns_a + 't')).strip()
                if line:
                    paragraphs.append(line)

            if paragraphs:
                slides_text.append(f'--- [슬라이드 {idx}] ---\n' + '\n'.join(paragraphs))

        return '\n\n'.join(slides_text)


# ---------------------------------------------------------------------------
# [STUDY-CUSTOM] 웹 아티클 HTML 본문 정제 및 파서
# ---------------------------------------------------------------------------
class _ArticleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip_tags = {'script', 'style', 'svg', 'noscript', 'nav', 'header', 'footer', 'aside'}
        self.current_skip = 0
        self.in_title = False
        self.title_parts = []
        self.text_parts = []
        self.block_tags = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'div', 'tr', 'article', 'section'}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.skip_tags:
            self.current_skip += 1
        elif tag == 'title':
            self.in_title = True
        elif tag in self.block_tags or tag == 'br':
            self.text_parts.append('\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.skip_tags:
            self.current_skip = max(0, self.current_skip - 1)
        elif tag == 'title':
            self.in_title = False
        elif tag in self.block_tags:
            self.text_parts.append('\n')

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        elif self.current_skip == 0:
            self.text_parts.append(data)


def _extract_html_text(raw: bytes) -> tuple[str, str]:
    """Parse HTML and return (title, clean_body_text)."""
    text = raw.decode('utf-8-sig', errors='replace')
    parser = _ArticleHTMLParser()
    parser.feed(text)
    title = ''.join(parser.title_parts).strip()
    body = ''.join(parser.text_parts)
    # 공백 및 연속 개행 정제
    body = re.sub(r'[ \t]+', ' ', body)
    body = re.sub(r'\n\s*\n', '\n\n', body).strip()
    return title, body


def fetch_web_article(url: str) -> tuple[str, str, bytes, str]:
    """
    [STUDY-CUSTOM] URL을 입력받아 본문을 스크랩하고 (제목, 가상파일명, 원본HTML바이트, 추출본문) 반환.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('유효한 HTTP 또는 HTTPS URL이어야 합니다.')

    host = parsed.netloc.split(':')[0].lower()
    # SSRF 방어: 로컬 및 사설 네트워크 주소 차단
    if host in ('localhost', '127.0.0.1', '::1') or host.startswith(('10.', '192.168.', '172.16.', '172.17.', '172.18.', '172.19.', '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.', '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.', '0.0.0.0')):
        raise ValueError('로컬 및 내부 네트워크 주소는 조회할 수 없습니다.')

    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'html' not in content_type and 'text' not in content_type:
                raise ValueError(f'지원하지 않는 웹 문서 형식입니다 ({content_type}).')
            raw = resp.read(MAX_URL_FETCH_BYTES + 1)
            if len(raw) > MAX_URL_FETCH_BYTES:
                raise ValueError('웹 페이지 크기가 10 MiB를 초과합니다.')
    except Exception as exc:
        raise ValueError(f'웹 페이지를 가져올 수 없습니다: {exc}') from exc

    title, body = _extract_html_text(raw)
    if not title:
        title = parsed.path.rstrip('/').split('/')[-1] or parsed.netloc
    filename = f"{re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:40]}.html"
    return title, filename, raw, body


def decode_document(filename, raw):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('파일은 1 byte~32 MiB여야 합니다.')
    suffix = Path(filename).suffix.lower()
    try:
        if suffix in {'.txt', '.md', '.csv', '.json', '.rst', '.log'}:
            text = raw.decode('utf-8-sig')
        elif suffix == '.docx':
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                info = archive.getinfo('word/document.xml')
                limit_error = 'DOCX 본문 XML은 압축 해제 후 16 MiB까지 지원합니다. 문서를 나누어 등록하세요.'
                if info.file_size > MAX_DOCX_XML_BYTES:
                    raise ValueError(limit_error)
                # Only the body is needed; never decompress images or attachments.
                try:
                    with archive.open(info) as source:
                        xml = source.read(MAX_DOCX_XML_BYTES + 1)
                except (RuntimeError, EOFError, zlib.error) as exc:
                    raise ValueError('DOCX 본문을 읽을 수 없습니다. 암호화·압축 방식이나 파일 손상을 확인하세요.') from exc
                if len(xml) > MAX_DOCX_XML_BYTES:
                    raise ValueError(limit_error)
                if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                    raise ValueError('DOCX XML 엔티티는 허용하지 않습니다.')
                root = ET.fromstring(xml)
                ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                def paragraph(node):
                    return ''.join('\t' if n.tag == ns + 'tab' else '\n' if n.tag in {ns + 'br', ns + 'cr'} else (n.text or '') if n.tag == ns + 't' else '' for n in node.iter())
                text = '\n'.join(paragraph(n) for n in root.iter(ns + 'p'))
        elif suffix == '.pptx':
            # [STUDY-CUSTOM] PPTX 슬라이드 파싱
            text = _extract_pptx_text(raw)
        elif suffix == '.zip':
            # [STUDY-CUSTOM] Obsidian 볼트 ZIP 파싱
            text = _extract_zip_vault_text(raw)
        elif suffix in {'.html', '.htm'}:
            # [STUDY-CUSTOM] HTML 본문 파싱
            _, text = _extract_html_text(raw)
        elif suffix == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise ValueError('암호화 PDF는 지원하지 않습니다.')
            if len(reader.pages) > 200:
                raise ValueError('PDF는 200쪽까지 지원합니다.')
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or '')
                if sum(map(len, parts)) > MAX_TEXT:
                    raise ValueError('추출 본문은 128,000자까지 분석할 수 있습니다. 문서를 나누어 등록하세요.')
            text = '\n'.join(parts)
        else:
            raise ValueError('지원 형식: TXT, MD, CSV, JSON, RST, LOG, PDF, DOCX, PPTX, HTML, ZIP')
    except (UnicodeError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError('문서 형식이 손상되었거나 UTF-8이 아닙니다.') from exc
    if not text.strip():
        raise ValueError('텍스트가 없습니다. 스캔 문서는 OCR 후 등록하세요.')
    if len(text) > MAX_TEXT or '\x00' in text:
        raise ValueError('텍스트는 128,000자 이내이며 NUL 문자를 포함할 수 없습니다.')
    return text


def chunks(text, size=8000):
    for start in range(0, len(text), size):
        yield start, text[start:start + size]


def bounded_spans(text, size, *, minimum=None, first=False):
    """Exact contiguous slices; prefer boundaries in the latter half of a window."""
    minimum = size // 2 if minimum is None else minimum
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            matches = list(re.finditer(r'\n|[.!?。！？](?:[ \t]|$)', text[start + minimum:end]))
            if matches:
                end = start + minimum + matches[0 if first else -1].end()
        yield start, text[start:end]
        start = end
