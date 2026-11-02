"""Unit tests for PPTX presentation parsing support."""
import io
import unittest
import zipfile

from verinote.documents import decode_document, _extract_pptx_text


class TestPPTXSupport(unittest.TestCase):
    def _create_mock_pptx(self, slides_content: list[list[str]]) -> bytes:
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            for idx, paras in enumerate(slides_content, 1):
                p_elements = ''.join(f'<a:p><a:r><a:t>{text}</a:t></a:r></a:p>' for text in paras)
                xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:sp><p:txBody><a:bodyPr/>{p_elements}</p:txBody></p:sp></p:spTree></p:cSld>
</p:sld>'''
                zf.writestr(f'ppt/slides/slide{idx}.xml', xml)
        return bio.getvalue()

    def test_pptx_slide_extraction(self):
        slides = [
            ['아키텍처 설계', 'MSA 기반 시스템 구조'],
            ['데이터 파이프라인', 'Kafka와 Flink 연동']
        ]
        raw = self._create_mock_pptx(slides)
        text = decode_document('presentation.pptx', raw)

        self.assertIn('--- [슬라이드 1] ---', text)
        self.assertIn('아키텍처 설계', text)
        self.assertIn('MSA 기반 시스템 구조', text)
        self.assertIn('--- [슬라이드 2] ---', text)
        self.assertIn('Kafka와 Flink 연동', text)

    def test_empty_pptx_raises_value_error(self):
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            zf.writestr('ppt/presentation.xml', '<p:presentation/>')
        raw = bio.getvalue()
        with self.assertRaises(ValueError):
            _extract_pptx_text(raw)


if __name__ == '__main__':
    unittest.main()
