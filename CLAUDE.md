# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트

AI 위험성평가 도우미 — 건설 현장 **불시·단발성 작업**용 위험성평가서를 자동 작성하는 웹앱. 사용자가 작업 정보를 입력하면 백엔드가 사내 위험성평가 DB에서 RAG로 유사 위험요인·대책을 검색한 뒤 Gemini로 위험요인·안전보건추진계획을 생성하고, 회사 표준 xlsx 양식에 채워서 다운로드용으로 반환한다.

- 전체 제품 스펙: `계획서.md` (한국어, 상세 명세 포함)
- 구현 결정 사항이 정리된 설계 문서: `docs/superpowers/specs/2026-04-28-risk-assessment-webapp-design.md`

## 저장소 구조

- `webapp/backend/` — FastAPI 백엔드 (실서비스용). 이 디렉토리의 `Dockerfile`과 `fly.toml`이 Fly.io 앱 `miucci-risk-assess`(Tokyo region)로 배포된다.
- `web/` — Next.js 16 (App Router) + React 19 + Tailwind v4 프론트엔드. 단일 페이지 폼은 `src/app/page.tsx`. **반드시 `web/AGENTS.md`를 먼저 읽을 것** — *프리릴리스* Next.js이므로 Next 13/14 관성으로 코드 짜지 말고 `node_modules/next/dist/docs/`를 먼저 확인한다.
- `최초위험성평가 기초자료-건축_REV1.xls` (루트) — 원본 위험성평가 DB (40개 시트, 공종 약 38종). 1회 변환 후 `webapp/backend/data/source/risk_db.xlsx` → ChromaDB로 인덱싱한다.
- `불시,단발성작업(양식).pdf` (루트) — 회사 표준 출력 양식 참고용 (TAEYOUNG/태영건설 로고).
- `docs/superpowers/plans/` — 백엔드/프론트엔드 구현 계획서 (한국어, 작업 이력).
- `CLAUDE_COMMANDS.md` — 사용자가 설치해둔 Superpowers + gstack 슬래시 명령어 한국어 치트시트.

## 백엔드 아키텍처

이하 경로는 모두 `webapp/backend/` 기준. 요청 파이프라인은 다음과 같다.

`main.py` (FastAPI) → `rag/retriever.py` (ChromaDB 질의 + 장비 키워드 재정렬) → `llm/generator.py` (Gemini 호출, JSON 응답 + thinking budget 설정) → 응답 `rows`, `sources`, `meta`. 다운로드는 별도 POST 엔드포인트로, 사용자가 편집했을 수도 있는 `rows`를 받아 `excel/writer.py`가 `template/위험성평가서_template.xlsx` + `template/cell_map.yaml`로 채워 반환한다.

여러 파일을 같이 봐야 알 수 있는 핵심 불변식:

- **cell_map.yaml이 템플릿 빌더와 라이터를 동시에 구동한다.** `excel/template_builder.py`가 이 YAML로 빈 템플릿을 *생성*하고, `excel/writer.py`가 같은 YAML로 그 템플릿을 *채운다*. 레이아웃을 바꾸면 반드시 `python -m excel.template_builder`로 템플릿을 다시 빌드해야 한다 — xlsx를 손으로 수정하지 말 것.
- **본문 행은 12행으로 하드캡되어 있다.** `body_start_row` 6 → `body_end_row` 17. `writer.fill_template`은 `rows[:12]`로 잘라내고, LLM 프롬프트도 최대 12개 출력을 가정한다. 늘리려면 템플릿 빌더도 같이 바꿔야 한다.
- **인제스트와 검색이 임베딩 함수를 공유한다.** `rag/retriever.py`가 `rag/ingest.py`의 `_get_embedding_function`을 임포트한다 — 한 컬렉션을 만들 때와 질의할 때 임베딩 종류(로컬 vs Gemini)가 같아야 한다. 선택자는 `use_local_embedding = not settings.gemini_api_key`이며 `main.assess`에서 결정된다. 한쪽으로 인제스트하고 다른 쪽으로 질의하면 벡터가 어긋난다.
- **Gemini 키 없는 모드는 실제 운영 경로다.** `settings.gemini_api_key`가 빈 문자열이면 `main.assess`가 로컬 임베딩을 쓰고, LLM 호출은 실패해 `generator.generate`가 RAG 원문 기반 `(fallback_rows, fallback_used=True)`를 반환한다. 테스트도 이 흐름을 가정한다 — `tests/test_api.py`는 가짜 키만 설정한다.
- **`thinking_level` → 모델·예산 매핑은 `llm/generator.py`에 있다.** `MODEL_MAP`, `THINKING_BUDGET_MAP` 참고. 요청에 `model_override`가 오면 그게 우선이다. `main.assess`도 응답 `meta`용으로 같은 계산을 다시 한다 — 레벨을 바꾸면 양쪽을 같이 고쳐야 한다.
- **XLS 원본은 레거시다.** `scripts/parse_xls.py`는 `xlrd==1.2.0`을 사용한다 (xlrd가 2.0에서 .xls 지원을 끊었기 때문에 핀 고정). 두 줄 병합 헤더를 `_find_header_rows` + `_build_column_names`로 처리하고 `COL_ALIASES`로 정규화한 뒤 `data/source/risk_db.xlsx`를 쓴다. xlrd 버전을 올리면 안 된다.

## 자주 쓰는 명령어

백엔드 명령은 모두 `webapp/backend/`에서 venv 활성화 (`source .venv/bin/activate`) 후 실행.

```bash
# 1회성 데이터 셋업
python -m scripts.parse_xls                      # 레거시 .xls → data/source/risk_db.xlsx
python -m rag.ingest                             # data/risk_db/에 ChromaDB 빌드 (--force로 재빌드)
python -m excel.template_builder                 # template/위험성평가서_template.xlsx (재)생성

# API 실행
uvicorn main:app --reload --port 8000

# 테스트 (전체 / 단일 파일 / 단일 케이스)
pytest                                           # tests/ 전체
pytest tests/test_api.py                         # 파일 단위
pytest tests/test_api.py::test_health_check -v   # 케이스 단위
```

프론트엔드 (`web/`):

```bash
npm run dev      # next dev (포트 3000)
npm run build    # next build
npm run lint     # eslint (eslint.config.mjs, flat config)
```

프론트엔드는 백엔드 URL을 `NEXT_PUBLIC_API_BASE` 환경변수에서 읽는다 (기본값 `http://127.0.0.1:8000`).

## 설정

백엔드 설정 (`config.py`, pydantic-settings)은 `webapp/backend/.env`에서 로드된다. 현재 쓰이는 변수:

- `GEMINI_API_KEY` — 빈 문자열이면 "로컬 임베딩 + 폴백 행" 경로로 동작한다 (위 불변식 참고).
- `CHROMA_PERSIST_DIR`, `SOURCE_XLSX_PATH`, `TEMPLATE_XLSX_PATH`, `CELL_MAP_PATH` — 백엔드 cwd 기준 상대 경로.
- `ALLOWED_ORIGINS` — 콤마 구분. CORS는 이와 별개로 `https://*.vercel.app`도 정규식으로 항상 허용한다.
- `GEMINI_GENERATION_MODEL` / `GEMINI_FAST_MODEL` / `GEMINI_EMBEDDING_MODEL`.

Dockerfile은 백엔드 전체를 `/app`으로 복사하고 `uvicorn main:app --host 0.0.0.0 --port 8000`을 실행한다. 단, `.dockerignore`가 `data/source/`와 `scripts/`를 제외한다 — 즉 배포된 이미지는 `data/risk_db/`에 ChromaDB가 이미 빌드돼 있어야 한다 (인제스트는 Fly에서 돌리는 게 아니라 로컬에서 미리 끝내고 빌드한다).

## 테스트

- 테스트는 `webapp/backend/tests/`에 있다. `conftest.py`가 백엔드 디렉토리를 `sys.path`에 추가해 `from main import app` 같은 임포트가 동작한다.
- `test_api.py`는 임시 디렉토리에 미니멀한 1행 ChromaDB + 템플릿을 만드는 `app_with_db` 픽스처를 쓰고, `GEMINI_API_KEY=test-fake-key`를 설정한 뒤 `/api/assess`와 `/api/download`를 end-to-end로 호출한다. Gemini 호출은 케이스별로 `patch`해서 끊는다 — API 테스트를 추가할 때 실제 LLM을 호출하지 말고 이 패턴을 따를 것.

## 배포

- **프론트엔드(`web/`)는 사용자가 "배포해줘"라고 하면 바로 production으로 올린다.** `web/`에서 `npx vercel deploy --prod --yes` 실행. Preview 배포(`--prod` 없이)는 사용자가 명시적으로 "preview 배포" / "테스트 배포"라고 했을 때만 한다.
- Vercel 프로젝트: `web` (`miucci0212-glitchs-projects`). `.vercel/project.json`에 연결돼 있어 추가 설정 불필요.
- 백엔드는 Fly.io 앱 `miucci-risk-assess` (Tokyo). 백엔드 배포 시에는 `webapp/backend/`에서 `flyctl deploy`. `data/risk_db/`(ChromaDB)가 빌드된 상태여야 한다.

## 작업 시 주의사항

- 사용자 표시 문구와 다수의 데이터 필드(시트명, 컬럼명, 에러 메시지 등)가 한국어다. 편집할 때 영어로 번역하지 말 것.
- `webapp/backend/.venv/`는 사실상 커밋 트리에 포함돼 있다 (gitStatus에 잡힘) — CI가 venv를 새로 만들어줄 것이라고 가정하지 말고, 기존 venv를 활성화해서 쓴다.
- 사용자는 Superpowers + gstack 슬래시 명령으로 작업한다. 선호 워크플로우(think → plan → build → review → test → ship)는 `CLAUDE_COMMANDS.md` 참고.
- 사용자가 "커밋" 또는 "푸쉬"를 요청하면 항상 `git commit` + `git push`를 함께 실행한다. 커밋만 만들고 멈추지 말 것.
