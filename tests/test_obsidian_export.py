"""Unit tests for Obsidian vault markdown export."""
import io
import unittest
import zipfile

from verinote.documents import decode_document
from verinote.export_obsidian import export_document_obsidian, export_vault_obsidian


class TestObsidianExport(unittest.TestCase):
    def test_export_document_obsidian(self):
        doc = {
            'id': 'doc-123',
            'title': '파이썬 아키텍처 가이드',
            'version': 1,
            'filename': 'python_guide.md',
            'items': [
                {
                    'kind': 'page',
                    'id': 'page-1',
                    'status': 'approved',
                    'payload': {
                        'title': 'FastAPI와 비동기',
                        'claims': [
                            {'heading': '이벤트 루프', 'text': 'FastAPI는 비동기 이벤트 루프 위에서 실행됩니다.', 'quote': '비동기 이벤트 루프'}
                        ]
                    }
                },
                {
                    'kind': 'fact',
                    'id': 'fact-1',
                    'status': 'approved',
                    'payload': {
                        'subject': 'FastAPI',
                        'predicate': 'depends_on',
                        'object': 'Uvicorn',
                        'quote': 'FastAPI depends on Uvicorn'
                    }
                },
                {
                    'kind': 'ontology',
                    'id': 'onto-1',
                    'status': 'approved',
                    'payload': {
                        'entities': [
                            {'id': 'FastAPI', 'name': 'FastAPI', 'type': '프레임워크'}
                        ],
                        'relations': []
                    }
                }
            ]
        }

        zip_bytes = export_document_obsidian(doc)
        self.assertGreater(len(zip_bytes), 0)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            self.assertIn('Index.md', names)
            self.assertIn('Wikis/FastAPI와 비동기.md', names)
            self.assertIn('Entities/FastAPI.md', names)

            index_content = zf.read('Index.md').decode('utf-8')
            self.assertIn('[[FastAPI와 비동기]]', index_content)
            self.assertIn('[[FastAPI]] --`depends_on`--> [[Uvicorn]]', index_content)

            wiki_content = zf.read('Wikis/FastAPI와 비동기.md').decode('utf-8')
            self.assertIn('FastAPI는 비동기 이벤트 루프 위에서 실행됩니다.', wiki_content)
            self.assertIn('💬 **원문 인용:**', wiki_content)

    def test_import_obsidian_vault_zip(self):
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            zf.writestr('Notes/Architecture.md', '# 시스템 구조\nMSA와 이벤트 기반 [[Kafka]]를 사용합니다.')
            zf.writestr('Notes/Database.md', '# 데이터베이스\n[[PostgreSQL]]과 캐시 [[Redis]] 연동 구조.')
            zf.writestr('.obsidian/app.json', '{"theme": "dark"}')  # 제외되어야 함

        raw_zip = bio.getvalue()
        text = decode_document('MyVault.zip', raw_zip)

        self.assertIn('--- [노트: Architecture.md] ---', text)
        self.assertIn('MSA와 이벤트 기반 [[Kafka]]를 사용합니다.', text)
        self.assertIn('--- [노트: Database.md] ---', text)
        self.assertIn('[[PostgreSQL]]과 캐시 [[Redis]] 연동 구조.', text)
        self.assertNotIn('app.json', text)


if __name__ == '__main__':
    unittest.main()

