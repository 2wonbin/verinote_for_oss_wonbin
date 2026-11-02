"""Unit tests for Obsidian vault markdown export."""
import io
import unittest
import zipfile

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


if __name__ == '__main__':
    unittest.main()
