# AI 위험성평가 도우미 웹앱 — 설계 문서

Date: 2026-04-28

## 개요

건설 현장의 불시·단발성 작업에 대한 위험성평가서를 AI가 자동 작성하는 웹앱.
사용자가 작업 정보를 입력하면 회사 보유 위험성평가 DB(엑셀)를 RAG로 검색해 표준 양식 xlsx를 반환한다.

원본 계획서: `계획서.md` (상세 스펙 전체 포함)

---

## 확정 결정 사항 (계획서 보완)

### XLS 파싱

- 환경: xlrd 2.0.2 설치됨 (`.xls` 미지원), LibreOffice 없음
- **해결책**: `requirements.txt`에 `xlrd==1.2.0` 고정. 가상환경(`venv`) 내에서만 사용.
- 변환 산출물: `data/source/risk_db.xlsx` (1회 변환 후 캐싱)

### 구현 순서 (Bottom-up)

```
1. 환경 셋업 (.env, venv, requirements.txt, package.json)
2. DB 파싱 + 정규화 스크립트 (parse_xls.py → risk_db.xlsx)
3. ChromaDB 인덱싱 (rag/ingest.py)
4. openpyxl 템플릿 자동 생성 (excel/template_builder.py)
5. FastAPI 백엔드 (/api/assess, /api/download)
6. Next.js 프론트엔드 (입력 폼 + 결과 편집 + 다운로드)
7. 통합 테스트 + 프롬프트 튜닝
```

Gemini API 키 없이도 1~3단계는 독립 실행 가능.

### Excel 템플릿 생성

- `openpyxl`로 PDF 양식 구조 재현 (셀 병합·테두리·폰트·로고 텍스트)
- 좌표 매핑: `template/cell_map.yaml` 외부화
- 결과물: `template/위험성평가서_template.xlsx`

### 개발 환경

- 백엔드: Python venv, `webapp/backend/`
- 프론트엔드: Next.js 14 App Router, `webapp/frontend/`
- DB: ChromaDB 로컬 영속화 (`webapp/backend/data/risk_db/`)
- Docker 없이 로컬 dev 서버로 시작

---

## 아키텍처 (계획서 4장과 동일)

```
프론트엔드 (Next.js 14)
    ↕ HTTP
백엔드 (FastAPI)
    ├── RAG: ChromaDB + Gemini text-embedding-004
    ├── LLM: gemini-2.5-pro / gemini-2.5-flash
    └── Excel: openpyxl 템플릿 클론
```

---

## 기술 스택

| 레이어 | 기술 |
|---|---|
| 프론트엔드 | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| 백엔드 | Python FastAPI |
| AI | Gemini API (gemini-2.5-pro, text-embedding-004) |
| 벡터 DB | ChromaDB (로컬) |
| 엑셀 생성 | openpyxl |
| XLS 파싱 | xlrd==1.2.0 (legacy) |

---

## 디렉터리 구조

```
위험성평가 모델/
├── 계획서.md
├── 최초위험성평가 기초자료-건축_REV1.xls
├── 불시,단발성작업(양식).pdf
├── 불시,단발성작업(양식).hwp
├── webapp/
│   ├── backend/
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   ├── .env.example
│   │   ├── rag/
│   │   │   ├── ingest.py
│   │   │   └── retriever.py
│   │   ├── llm/
│   │   │   └── generator.py
│   │   ├── excel/
│   │   │   ├── template_builder.py
│   │   │   └── writer.py
│   │   ├── template/
│   │   │   ├── cell_map.yaml
│   │   │   └── 위험성평가서_template.xlsx (생성됨)
│   │   ├── data/
│   │   │   ├── source/
│   │   │   │   └── risk_db.xlsx (변환됨)
│   │   │   └── risk_db/ (ChromaDB)
│   │   └── scripts/
│   │       └── parse_xls.py
│   └── frontend/
│       ├── app/
│       │   └── page.tsx
│       ├── components/
│       │   ├── AssessForm.tsx
│       │   └── ResultTable.tsx
│       └── package.json
└── docs/
    └── superpowers/specs/
        └── 2026-04-28-risk-assessment-webapp-design.md
```

---

## API 명세

`POST /api/assess` — RAG 검색 + LLM 생성, JSON 반환 (미리보기)
`POST /api/download` — 동일 입력으로 xlsx 파일 반환

상세 요청/응답 스펙은 계획서 8장 참조.

---

## 에러 처리

- LLM JSON 파싱 실패: 1회 자기수정 호출 → 그래도 실패 시 RAG 원문 fallback
- RAG 결과 5건 미만: 공종 필터 해제 후 전체 인덱스 재검색
- xlrd .xls 파싱 실패: 명확한 에러 메시지 + 재변환 지시

---

## 테스트 전략

| 계층 | 도구 |
|---|---|
| 단위 | pytest (retriever, writer, generator) |
| 통합 | pytest + httpx (/api/assess, /api/download) |
| 프론트 e2e | Playwright |
| LLM 회귀 | 골든 케이스 5건 (nightly) |

---

## 환경변수 (.env)

```
GEMINI_API_KEY=          # 나중에 추가
GEMINI_GENERATION_MODEL=gemini-2.5-pro
GEMINI_FAST_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=text-embedding-004
CHROMA_PERSIST_DIR=./data/risk_db
SOURCE_XLSX_PATH=./data/source/risk_db.xlsx
TEMPLATE_XLSX_PATH=./template/위험성평가서_template.xlsx
CELL_MAP_PATH=./template/cell_map.yaml
LLM_TIMEOUT_SEC=60
RATE_LIMIT_PER_MIN=10
ALLOWED_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
```
