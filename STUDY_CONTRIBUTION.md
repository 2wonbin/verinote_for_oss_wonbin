# 📘 Verinote 오픈소스 스터디 기여 및 개선 보고서
**— Windows 실전 트러블슈팅과 PKM 관점의 창발적 지식 엔진 확장 —**

---

## 📌 목차
1. [프로젝트 개요 및 포크 목적](#1-프로젝트-개요-및-포크-목적)
2. [PART 1. 실전 트러블슈팅 로그 (Troubleshooting)](#part-1-실전-트러블슈팅-로그-troubleshooting)
   - 1.1 [WinError 5] 원자적 파일 교체(atomic_json) 권한 충돌
   - 1.2 [WinError 206] CLI 명령행 32KB 길이 제한 초과
   - 1.3 LLM 토큰 글리치(한자 衰) 및 JSON 파싱 에러
   - 1.4 Datalog 엔진 `'<' not supported between instances of 'int' and 'str'` 에러
   - 1.5 `Unresolvable context meaning reference` 컨텍스트 검증 예외
   - 1.6 `전이 질의에는 기준 개체와 관계를 지정하세요` 제약 완화
3. [PART 2. 신규 커스텀 기능 구현 내역 (Custom Features)](#part-2-신규-커스텀-기능-구현-내역-custom-features)
   - 2.1 PPTX 프레젠테이션 슬라이드 파서 내장
   - 2.2 웹 아티클 / 기술 블로그 URL 스크랩 등록 기능
   - 2.3 순수 HTML5 Canvas 기반 인터랙티브 지식 그래프 뷰어
   - 2.4 Obsidian Vault 쌍방향 연동 (Export & Import) 및 통합 모달
   - 2.5 질문 이력 스크롤 격리 및 지능형 관계 탐색 UI 개편
   - 2.6 Datalog 복합 전이 추론 및 2-Tier 창발적 통찰 시스템
4. [아키텍처 및 철학적 통찰 (Lessons Learned)](#4-아키텍처-및-철학적-통찰-lessons-learned)

---

## 1. 프로젝트 개요 및 포크 목적

* **프로젝트명**: `Verinote` (근거 기반 위키 + Wirelog Datalog 추론 지식 관리 시스템)
* **기반 기술**: Python 3.13, SQLite, PyreWire (Datalog 추론 엔진), Pure Vanilla JS / CSS, Antigravity CLI (`agy`) / Copilot / Claude
* **포크 목적**:
  1. **Windows 환경 완벽 호환**: POSIX/리눅스 중심 설계로 인해 Windows 네이티브 환경에서 발생하는 치명적 OS 버그 해결.
  2. **개인 지식 관리(PKM) 확장**: 텍스트 파일 외 PPTX, 웹 URL, Obsidian 볼트와의 상호운용성 확보.
  3. **창발적 지식(Emergent Knowledge) 도출**: 지나치게 폐쇄적인 Datalog 단일 predicate 제약과 '입틀막' 프롬프트를 절충하여, 흩어진 문서들을 엮어 새로운 통찰을 이끌어내는 차세대 지식 엔진으로 진화.

---

## PART 1. 실전 트러블슈팅 로그 (Troubleshooting)

### 1.1 [WinError 5] 원자적 파일 교체(atomic_json) 권한 충돌
* **증상**: 에이전트 실행 및 질문 완료 후 `[WinError 5] 액세스가 거부되었습니다: 'usage.json.tmp' -> 'usage.json'` 예외 발생.
* **원인**: Windows 파일 시스템(NTFS)은 프로세스나 안티바이러스가 파일 핸들을 닫는 순간 일시적인 핸들 잠금(Transient Lock)을 유지합니다. 이때 `Path.replace()`를 즉시 호출하면 OS 레벨에서 권한 거부가 발생합니다.
* **해결책 (`verinote/usage.py`)**:
  - `atomic_json` 함수에 지수 백오프(Exponential Backoff: 0.02초 ~ 0.1초, 5회) 재시도 루프를 적용하여 Windows 파일 잠금이 해제될 때까지 안전하게 대기 후 교체하도록 패치.

### 1.2 [WinError 206] CLI 명령행 32KB 길이 제한 초과
* **증상**: 프롬프트가 길어질 때 `[WinError 206] 파일 이름이나 확장명이 너무 깁니다` 에러와 함께 답변 생성 실패.
* **원인**: Windows `CreateProcess` API의 명령행 문자열 최대 길이는 **32,767자**입니다. 대용량 문서와 스키마가 포함된 18,000자 이상의 프롬프트를 `agy -p "<PROMPT>"` 인자로 전달하면서 한도를 초과했습니다.
* **해결책 (`verinote/agents.py`)**:
  - `command()` 함수에서 Windows 플랫폼일 때 `copilot`처럼 `agy`도 명령행 인자 대신 **`stdin` 파이프(표준 입력)**로 프롬프트를 넘기도록 수정.

### 1.3 LLM 토큰 글리치(한자 衰) 및 JSON 파싱 에러
* **증상**: `Expecting ',' delimiter: line 1 column 395 (char 394)`
* **원인**: 18,000자에 달하는 복잡한 시스템 프롬프트를 경량 모델이 처리하는 과정에서, JSON 닫는 괄호 직전에 뜬금없는 한자 글리치(`衰}`)가 출력되어 파싱 실패.
* **해결책**:
  - 고지능 모델(`gemini-3.8-flash-high`) 권장 및 JSON 정규화 프로세스 가이드 수립.

### 1.4 Datalog 엔진 `'<' not supported between instances of 'int' and 'str'` 에러
* **증상**: 복합 경로 질의 시 `TypeError: '<' not supported between instances of 'int' and 'str'` 발생 및 답변 생성 실패.
* **원인**: Datalog 추론 엔진(`PyreWire`)이 새로 추가된 Datalog 규칙 `flow_reach(X, "flow", Z)`의 `"flow"` 문자열 리터럴을 내부 심볼 번호인 **정수 `3` (`int`)**으로 반환했습니다. 파이썬 `engine.py`에서 기존 문자열 관계(`'relation:xxx'`, `str`)들과 정수가 섞인 튜플 목록을 `sorted()` 하려다 타입 비교 예외가 발생.
* **해결책 (`verinote/engine.py`)**:
  - Datalog 스냅샷 결과를 받을 때 내부 정수 심볼을 안전하게 문자열 `'flow'`로 정규화하는 `tuple('flow' if isinstance(x, int) else str(x) for x in r)` 변환 로직 추가.

### 1.5 `Unresolvable context meaning reference` 컨텍스트 검증 예외
* **증상**: 질문 실행 시 `Unresolvable context meaning reference` 에러와 함께 답변 미생성.
* **원인**: `verinote/question_context.py`의 `_validate_graph`는 반환된 그래프의 모든 관계(`row[1]`)가 공식 사전 스키마(`result['relations']`)에 실존하는지 엄격히 검사합니다. 새로 계산된 합성 전이 관계 `'flow'`에 대한 스키마 메타데이터 객체가 누락되어 검증에 탈락.
* **해결책 (`verinote/engine.py`)**:
  - 그래프 질의 결과에 `'flow'` 관계가 포함될 경우, 검증 규격에 부합하는 합성 관계 스키마 객체(`synthetic flow relation`)를 `result['relations']`에 자동으로 동봉하도록 보강.

### 1.6 `전이 질의에는 기준 개체와 관계를 지정하세요` 제약 완화
* **증상**: LLM 또는 사용자가 복합 경로를 탐색하려 할 때 폼/백엔드 유효성 에러 발생.
* **원인**: 엔진은 관계(`predicate`)가 비어있어도 전체 흐름을 찾을 수 있게 개선했으나, `verinote/assistant.py` (280행)와 프론트엔드 `app.js`에서 여전히 `predicate` 입력을 필수로 강제하고 있었음.
* **해결책**: `assistant.py`와 `app.js`에서 관계 필수를 선택 사항으로 완화하여, 비워두면 "모든 관계를 잇는 종합 전이 흐름"으로 자연스럽게 작동하도록 개선.

---

## PART 2. 신규 커스텀 기능 구현 내역 (Custom Features)

### 2.1 PPTX 프레젠테이션 슬라이드 파서 내장
* **구현 파일**: `verinote/documents.py`, `tests/test_pptx.py`
* **기술적 특징**:
  - 무거운 서드파티 라이브러리(`python-pptx` 등) 없이, Python 표준 라이브러리인 `zipfile`과 `xml.etree.ElementTree`만을 사용하여 `.pptx` 파일 내부의 `ppt/slides/slide*.xml`을 순서대로 파싱.
  - 슬라이드별 본문 텍스트를 구조화하여 추출하고, 텍스트 크기 한도(16 MiB) 및 XML 폭탄 방어 로직 내장.

### 2.2 웹 아티클 / 기술 블로그 URL 스크랩 등록 기능
* **구현 파일**: `verinote/server.py`, `verinote/documents.py`, `verinote/web/app.js`, `verinote/web/index.html`
* **기술적 특징**:
  - `POST /api/documents/fetch-url` 엔드포인트 신설.
  - 무거운 headless 브라우저(Puppeteer, Playwright) 없이 순수 Python의 `urllib.request`와 `html.parser`로 웹 아티클 본문 추출.
  - `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>` 등 불필요한 태그를 자동 제거하고, 본문 컨테이너(`<article>`, `<main>`)를 우선 탐색하는 경량 파서 구현.

### 2.3 순수 HTML5 Canvas 기반 인터랙티브 지식 그래프 뷰어
* **구현 파일**: `verinote/web/graph.js`, `verinote/web/index.html`, `verinote/web/style.css`
* **기술적 특징**:
  - 외부 거대 라이브러리(D3.js, Cytoscape.js 등) 의존성을 일절 배제한 **순수 HTML5 Canvas 기반 Force-directed layout 물리 시뮬레이션** 자체 구현.
  - **기능**:
    - 쿨롱 반발력과 훅 탄성 스프링 모델을 통한 노드 자동 배치.
    - 마우스 드래그 앤 드롭 노드 위치 고정/이동.
    - 마우스 휠 부드러운 줌인/줌아웃(Zoom in/out) 및 캔버스 패닝(Panning).
    - 관계선(Edge) 또는 노드 호버/클릭 시 원문 인용문과 출처를 보여주는 인터랙티브 툴팁 팝업.

### 2.4 Obsidian Vault 쌍방향 연동 (Export & Import) 및 통합 모달
* **구현 파일**: `verinote/export_obsidian.py`, `verinote/documents.py`, `verinote/web/index.html`, `verinote/web/app.js`
* **기술적 특징**:
  - **내보내기 (Export)**: 승인된 위키 문서와 사실(Fact)들을 옵시디언 표준 규격인 **`[[WikiLinks]]` 및 YAML Frontmatter(태그/별칭)**가 포함된 볼트 디렉터리 구조로 묶어 `.zip`으로 다운로드.
  - **불러오기 (Import)**: 기존 사용자가 작성한 Obsidian 볼트 ZIP을 업로드하면 시스템 폴더(`.obsidian` 등)를 자동 필터링하고 본문 내 `[[위키링크]]`를 보존한 채 새 문서로 등록.
  - **UI 개선**: 단정한 서브 버튼(`.btn-obsidian`)과 직관적인 노트북 이모지(`📓`)를 적용한 일원화 연동 모달 창 제공.

### 2.5 질문 이력 스크롤 격리 및 지능형 관계 탐색 UI 개편
* **구현 파일**: `verinote/web/app.js`, `verinote/web/index.html`, `verinote/web/style.css`
* **기술적 특징**:
  - **질문 이력 스크롤 박스**: 질문이 쌓일수록 페이지가 무한정 길어지는 현상을 방지하기 위해 `max-height: 260px` 스크롤 박스 및 `<details>` 아코디언 접기 적용.
  - **개체/관계 자동완성 (Datalist 지원)**: 승인된 그래프 메타데이터를 분석하여 `기준 개체`, `관계`, `도착 개체` 입력창에 `<datalist>` 추천 드롭다운 연동.
  - **빠른 개체 선택 칩 (Chips)**: 등록된 주요 개체들을 둥근 칩 버튼으로 나열하여 클릭 한 번으로 입력.
  - **🗺️ 원클릭 전체 지식 그래프 버튼**: 복잡한 폼을 고민할 필요 없이 현재 승인된 전체 지식을 Canvas로 즉시 시각화.

### 2.6 Datalog 복합 전이 추론 및 2-Tier 창발적 통찰 시스템
* **구현 파일**: `verinote/rules.dl`, `verinote/engine.py`, `verinote/assistant.py`, `verinote/web/app.js`, `verinote/web/style.css`
* **기술적 특징**:
  - **Datalog 복합 전이 규칙 (`verinote/rules.dl`)**:
    ```prolog
    flow_reach(X, P, Y) :- edge(X, P, Y).
    flow_reach(X, "flow", Z) :- edge(X, _, Y), flow_reach(Y, _, Z).
    ```
    - 서로 다른 관계 이름(`calls`, `emits_to`, `streams_to`)이라도 파이프라인 흐름상 이어지면 `reach`를 끊지 않고 연결하여 도달 경로를 계산.
  - **2-Tier 답변 시스템 (`verinote/assistant.py`, `app.js`)**:
    - **Tier 1 (증명된 팩트)**: 문서에서 직접 인용한 `🏛️ 승인 그래프 팩트`, `📄 승인 위키 팩트` 제시.
    - **Tier 2 (창발적 통찰 / 추론)**: 복수 문서의 팩트들을 종합하여 도출한 `💡 창발적 통찰 / 추론`(`kind: 'inference'`)을 시각적으로 강조된 푸른색 카드로 제공.

---

## 4. 아키텍처 및 철학적 통찰 (Lessons Learned)

> **"신뢰도 100%의 족쇄에서 실용적 창발의 날개로"**

1. **원작의 설계 철학 (극단적 결정론과 폐쇄 세계 가정)**:
   - Verinote 원작은 특허 분쟁, 금융 감사 등 **"법적 증거 책임(xAI)"**을 다투는 도메인을 목표로 하여, 거짓 추론(False Positive)을 막기 위해 동일 관계명 제한, 도구 10회 캡, 엄격한 "확인 불가"를 적용했습니다.
2. **개인 지식 관리(PKM)에서의 딜레마**:
   - 하지만 개인이 지식을 축적하고 아키텍처를 탐색할 때는 단순히 "A가 문서에 있나요?"를 확인하는 것보다, **"A 문서와 B 문서를 넣었을 때 내가 미처 몰랐던 영향도와 인과관계 C가 창발되는 것"**이 본질적인 효용입니다.
3. **우리의 절충 해법**:
   - 우리는 원작이 가진 **강력한 근거 추적성(Provenance Trace)**을 1%도 훼손하지 않으면서,
   - Datalog의 다중 관계 전이(`flow_reach`)와 프롬프트의 2-Tier 분리 답변 구조를 접목하여 **"100% 무결한 팩트 증명"과 "유연한 창발적 지식 인사이트"라는 두 마리 토끼를 모두 잡는 데 성공**했습니다.

---
*작성일자: 2026년 11월 02일 | Verinote OSS 포크 스터디 프로젝트*
