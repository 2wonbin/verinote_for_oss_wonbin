"""
[STUDY-CUSTOM] Obsidian Vault Markdown Export Module
Exports approved wikis and knowledge graphs as an Obsidian-compatible zip bundle with [[WikiLinks]].
"""
import io
import re
import zipfile
from datetime import datetime


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', name).strip()
    return cleaned[:80] or 'Untitled'


def export_document_obsidian(doc: dict) -> bytes:
    """Export a single document's approved wikis and facts as an Obsidian zip archive."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        doc_title = doc.get('title', '문서')
        items = doc.get('items', [])
        approved_pages = [i for i in items if i['kind'] == 'page' and i.get('status') == 'approved']
        approved_facts = [i for i in items if i['kind'] == 'fact' and i.get('status') == 'approved']
        ontology = next((i for i in items if i['kind'] == 'ontology' and i.get('status') == 'approved'), None)

        # 1. Index.md
        index_lines = [
            '---',
            f'title: "{doc_title}"',
            f'document_id: "{doc.get("id")}"',
            f'version: {doc.get("version")}',
            f'exported_at: "{datetime.now().isoformat()}"',
            'tags:',
            '  - verinote/document',
            '---',
            '',
            f'# {doc_title} (v{doc.get("version")})',
            '',
            f'- **파일명:** `{doc.get("filename", "")}`',
            f'- **승인된 위키 문서:** {len(approved_pages)}개',
            f'- **승인된 관계 사실:** {len(approved_facts)}개',
            '',
            '## 📚 위키 목차 (Map of Content)',
        ]
        if approved_pages:
            for p in approved_pages:
                title = p['payload'].get('title', '무제')
                index_lines.append(f'- [[{title}]]')
        else:
            index_lines.append('*승인된 위키 문서가 아직 없습니다.*')

        index_lines.extend(['', '## 🕸️ 지식 그래프 관계 요약'])
        if approved_facts:
            for f in approved_facts:
                py = f['payload']
                s, p, o = py.get('subject'), py.get('predicate'), py.get('object')
                index_lines.append(f'- [[{s}]] --`{p}`--> [[{o}]]')
        else:
            index_lines.append('*승인된 관계 사실이 아직 없습니다.*')

        zf.writestr('Index.md', '\n'.join(index_lines))

        # 2. 위키 문서들 ({title}.md)
        for page in approved_pages:
            py = page['payload']
            title = py.get('title', '무제')
            claims = py.get('claims', [])
            fname = f'Wikis/{_sanitize_filename(title)}.md'

            # 이 위키와 연관된 관계들 필터링
            related_facts = [f for f in approved_facts if any(f['payload'].get(k) in title for k in ('subject', 'object'))]

            lines = [
                '---',
                f'title: "{title}"',
                f'document: "{doc_title}"',
                f'page_id: "{page.get("id")}"',
                'tags:',
                '  - verinote/wiki',
                '---',
                '',
                f'# {title}',
                '',
                '## 📝 주장 및 설명 (Claims)',
            ]
            for c in claims:
                heading = c.get('heading', '')
                text = c.get('text', '')
                quote = c.get('quote', '')
                if heading:
                    lines.append(f'### {heading}')
                if text:
                    lines.append(text)
                if quote:
                    lines.append(f'> 💬 **원문 인용:**\n> {quote}')
                lines.append('')

            if related_facts:
                lines.extend(['## 🔗 연관 관계 (Knowledge Graph)', ''])
                for f in related_facts:
                    py_f = f['payload']
                    s, pred, o = py_f.get('subject'), py_f.get('predicate'), py_f.get('object')
                    lines.append(f'- [[{s}]] --`{pred}`--> [[{o}]]')
                    if py_f.get('quote'):
                        lines.append(f'  > {py_f["quote"]}')
                lines.append('')

            zf.writestr(fname, '\n'.join(lines))

        # 3. 사전 엔티티들 (Entities/{id}.md)
        if ontology:
            ent_list = ontology['payload'].get('entities', [])
            for ent in ent_list:
                eid = ent.get('id', '')
                ename = ent.get('name', eid)
                etype = ent.get('type', 'entity')
                fname = f'Entities/{_sanitize_filename(eid)}.md'

                ent_lines = [
                    '---',
                    f'id: "{eid}"',
                    f'name: "{ename}"',
                    f'type: "{etype}"',
                    'tags:',
                    '  - verinote/entity',
                    f'  - verinote/type/{_sanitize_filename(etype)}',
                    '---',
                    '',
                    f'# {ename} ({etype})',
                    '',
                    f'- **공식 ID:** `{eid}`',
                    f'- **개체 타입:** `{etype}`',
                ]
                zf.writestr(fname, '\n'.join(ent_lines))

    return bio.getvalue()


def export_vault_obsidian(store) -> bytes:
    """Export the entire Verinote workspace into an Obsidian vault zip."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        docs = store.documents()
        snapshot = store.snapshot()
        all_facts = snapshot.get('facts', [])

        # 1. Main Vault Index
        index_lines = [
            '---',
            'title: "Verinote Knowledge Vault"',
            f'exported_at: "{datetime.now().isoformat()}"',
            f'total_documents: {len(docs)}',
            f'total_facts: {len(all_facts)}',
            'tags:',
            '  - verinote/vault',
            '---',
            '',
            '# 🗂️ Verinote 개인 지식 서재 (Obsidian Vault)',
            '',
            'Verinote에서 사람이 직접 검증하고 승인한 신뢰할 수 있는 지식 네트워크입니다.',
            '',
            '## 📄 문서 목록 (Documents)',
        ]
        for d in docs:
            index_lines.append(f'- [[Documents/{_sanitize_filename(d["title"])}|{d["title"]}]] (v{d["current_version"]})')

        index_lines.extend(['', '## 🌐 전체 지식 그래프 관계 요약', ''])
        for f in all_facts[:100]:
            py = f.get('payload', {})
            s, p, o = py.get('subject'), py.get('predicate'), py.get('object')
            index_lines.append(f'- [[{s}]] --`{p}`--> [[{o}]]')

        zf.writestr('Home.md', '\n'.join(index_lines))

        # 2. 문서별 상세 및 위키 파일들
        for d in docs:
            doc_data = store.document(d['id'])
            doc_title = doc_data['title']
            items = doc_data.get('items', [])
            approved_pages = [i for i in items if i['kind'] == 'page' and i.get('status') == 'approved']
            approved_facts = [i for i in items if i['kind'] == 'fact' and i.get('status') == 'approved']

            doc_path = f'Documents/{_sanitize_filename(doc_title)}.md'
            doc_lines = [
                '---',
                f'title: "{doc_title}"',
                f'version: {doc_data["version"]}',
                'tags:',
                '  - verinote/document',
                '---',
                '',
                f'# {doc_title}',
                '',
                f'- **원본 파일:** `{doc_data.get("filename", "")}`',
                f'- **승인된 위키 문서:** {len(approved_pages)}개',
                '',
                '## 위키 목록',
            ]
            for p in approved_pages:
                t = p['payload'].get('title', '무제')
                doc_lines.append(f'- [[Wikis/{_sanitize_filename(t)}|{t}]]')
            zf.writestr(doc_path, '\n'.join(doc_lines))

            # 개별 위키들
            for p in approved_pages:
                t = p['payload'].get('title', '무제')
                claims = p['payload'].get('claims', [])
                wiki_lines = [
                    '---',
                    f'title: "{t}"',
                    f'document: "{doc_title}"',
                    'tags:',
                    '  - verinote/wiki',
                    '---',
                    '',
                    f'# {t}',
                    '',
                    f'*출처 문서:* [[Documents/{_sanitize_filename(doc_title)}|{doc_title}]]',
                    '',
                    '## 설명 및 주장 (Claims)',
                ]
                for c in claims:
                    if c.get('heading'):
                        wiki_lines.append(f'### {c["heading"]}')
                    if c.get('text'):
                        wiki_lines.append(c['text'])
                    if c.get('quote'):
                        wiki_lines.append(f'> 💬 **원문 인용:**\n> {c["quote"]}')
                    wiki_lines.append('')
                zf.writestr(f'Wikis/{_sanitize_filename(t)}.md', '\n'.join(wiki_lines))

    return bio.getvalue()

