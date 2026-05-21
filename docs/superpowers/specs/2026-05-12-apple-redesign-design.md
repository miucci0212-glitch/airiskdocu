# 프론트엔드 Apple 재디자인 — 설계

## 배경

`web/` (Next.js 16 + React 19 + Tailwind v4) 단일 페이지를 Apple **macOS 시스템 설정 스타일**로 재단장한다. 루트에 방금 설치된 `DESIGN.md`(Apple-inspired 디자인 시스템)를 토큰 출처로 사용한다.

기존 페이지는 폼 16개 필드 + "위험성평가 생성" 버튼 + 회사 표준 양식 미리보기(다운로드 Excel과 동일한 헤더/본문/서명 테이블) + RAG 출처 details로 구성된다. 기능과 데이터 흐름은 그대로 유지하고 **UI만** 재설계한다. 백엔드, Excel 라이터, 인제스트 코드는 손대지 않는다.

## 목표

- DESIGN.md의 컬러·타이포·간격 토큰을 Tailwind v4 `@theme`에 연결한다.
- 폼을 4개 카드(현장 정보 / 작업 정보 / 결재 / AI 설정)로 그룹화하고, 각 카드 내부를 시스템 설정의 list row 패턴으로 구성한다.
- 회사 양식 미리보기도 애플풍(헤어라인, SF Pro, 액션 블루 포인트)으로 재스타일. 단, **Excel 출력물 자체는 그대로**(템플릿/writer 미수정).
- 하단 sticky action bar(생성 / 다운로드 pill 버튼) 도입.
- 다크모드 제거(라이트 전용).

## 비목표

- 백엔드 API 시그니처 변경 없음. `runAssess`/`download`가 호출하는 엔드포인트, 요청/응답 스키마는 동일.
- Excel 템플릿 (`webapp/backend/template/`) 미수정.
- 새 라우트, 모달, 라우팅 변경 없음. 단일 페이지 유지.
- 다국어, 다크모드, 토스트/스낵바 등 새 기능 추가 없음.

## 비주얼 언어

DESIGN.md에서 채택한 토큰:

| 카테고리 | 토큰 | 값 |
|---|---|---|
| 색 | `canvas-parchment` | `#f5f5f7` (페이지 배경) |
| 색 | `canvas` | `#ffffff` (카드) |
| 색 | `surface-pearl` | `#fafafc` (카드 내부 라벨/짝수행) |
| 색 | `ink` | `#1d1d1f` (본문) |
| 색 | `ink-muted-48` | `#7a7a7a` (보조 텍스트) |
| 색 | `ink-muted-80` | `#333333` (에러 본문 등) |
| 색 | `hairline` | `#e0e0e0` (모든 보더) |
| 색 | `divider-soft` | `#f0f0f0` (카드 내부 row 구분선) |
| 색 | `primary` | `#0066cc` (액션 블루) |
| 색 | `primary-focus` | `#0071e3` (focus 보더) |
| 색 | `on-primary` | `#ffffff` |
| 색 | `surface-chip-translucent` | `#d2d2d7` (segmented control 트랙은 `#e8e8ed`로 살짝 더 밝게) |
| 반경 | `rounded-md` | `11px` (입력) |
| 반경 | `rounded-lg` | `18px` (카드) |
| 반경 | `rounded-pill` | `9999px` (버튼·칩) |
| 간격 | 카드 사이 | `24px` |
| 간격 | 카드 내 row 패딩 | `12px 16px` |

**폰트**: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif`. macOS/iOS에서 SF Pro로 렌더, 그 외는 시스템 산세리프 폴백. Geist는 제거.

**그림자**: 없음. 단, "회사 양식 미리보기" 카드 1군데에만 매우 미세한 `0 1px 2px rgba(0,0,0,0.04)` 허용.

**다크모드**: 미지원. `globals.css`의 `@media (prefers-color-scheme: dark)` 블록 제거.

## 페이지 구조

```
slim top bar (흰색, 아래 헤어라인, 고정 아님)
  └ 좌: "AI 위험성평가 도우미" (display-md급)
  └ 우: "불시 · 단발성 작업" (caption, ink-muted-48)

main (max-w-3xl, mx-auto, px-6, py-8, bg-canvas-parchment)
  ├ 카드: 현장 정보
  ├ 카드: 작업 정보
  ├ 카드: 결재 라인
  ├ 카드: AI 설정
  ├ (생성 후) meta 칩 row
  ├ (생성 후) 카드: 회사 양식 미리보기
  └ (생성 후) RAG 출처 details

sticky action bar (bottom-0, white/80 + backdrop-blur, 위에 헤어라인)
  └ 좌측 정렬: [위험성평가 생성] (primary pill) [엑셀 다운로드] (secondary pill)
```

`max-w-3xl`(768px)로 폭을 좁게 잡아 시스템 설정의 단일 컬럼 느낌을 낸다. 모바일에서는 `px-4`.

## 폼 그룹화

기존 16개 필드 → 4개 카드:

### 현장 정보
- 현장명 (text)
- 업체명 (text)
- 공종 (text)
- 작업 책임자 (text)

### 작업 정보
- 작업기간 시작 (date)
- 작업기간 종료 (date)
- 작업인원 (number)
- 건설기계 종류 및 댓 수 (text)
- 근로자 (text, 쉼표 구분)
- 기계/기구 및 위험물질 (text, 쉼표 구분)
- 작업장소 (text, 쉼표 구분)
- 작업내용 (textarea, 3행)

### 결재 라인
- 안전관리자 (text, 선택)
- 관리감독자 (text, 선택)
- 현장소장 (text, 선택)

### AI 설정
- 사고 강도 (**segmented control**: fast / balanced / thorough / max)
- AI 모델 선택 (select, 옵션 그대로)

## 컴포넌트 명세

`web/src/app/page.tsx`에 모두 인라인으로 둔다(별도 파일 분리 안 함, 페이지 1개라 과한 추상화 회피).

### `<Card>`
- props: `title: string`, `children: ReactNode`
- 스타일: `bg-white rounded-[18px] border border-hairline`
- 상단: 그룹 제목 (`caption-strong`, 14px semibold, ink-muted-80, `px-5 pt-4 pb-2`)
- 내부: row 들 사이 `border-t border-divider-soft`

### `<Row label="...">`
- 한 줄 = `라벨 (왼쪽 고정폭) | 입력 (오른쪽 fill)`
- 스타일: `flex items-center gap-4 px-5 py-3`, 라벨 `w-32 shrink-0 text-ink-muted-80 text-[14px]`
- textarea 같이 높이 큰 input은 `<Row block label="..." />`로 위→아래 스택.

### `<TextField>`
- `<input type="..." />` 래퍼
- 스타일: `w-full rounded-[11px] border border-hairline px-3 py-2 text-[15px] bg-white`
- focus: `outline-none border-primary-focus ring-2 ring-primary-focus/25`

### `<SegmentedControl options value onChange>`
- 트랙: `flex p-1 bg-[#e8e8ed] rounded-[11px]`
- 옵션: `flex-1 py-1.5 text-[13px] rounded-[8px] text-ink-muted-80`
- 선택된 옵션: `bg-white text-ink shadow-[0_1px_2px_rgba(0,0,0,0.04)] font-medium`
- 비선택: 투명 배경, hover 시 미세 톤

### `<PillButton variant="primary" | "secondary" loading>`
- 공통: `rounded-full px-6 py-2.5 text-[15px] font-medium inline-flex items-center gap-2`
- primary: `bg-primary text-white hover:bg-primary-focus`
- secondary: `bg-white text-primary border border-hairline hover:bg-surface-pearl`
- disabled: `opacity-40 cursor-not-allowed`
- loading: 좌측에 얇은 ring spinner(stroke 2px), 텍스트는 opacity 50로 dim(invisible 처리 X — 너비 흔들림 방지)

### `<MetaChip>`
- `inline-flex items-center gap-1.5 rounded-full bg-ink text-white px-3 py-1 text-[12px]`
- 폴백 칩만 `bg-amber-100 text-amber-800`(예외)

## 회사 양식 미리보기 재스타일

전체를 `<Card>` 1개 안에 감싼다. 내부 테이블의 구조(헤더 행 / 메타 정보 / 본문 12행 / 서명 푸터)는 보존. 변경되는 비주얼만 명시:

- 모든 검정 2px 보더 → `border border-hairline` (1px)
- 헤더 행:
  - 로고 셀: TAEYOUNG/태영건설 텍스트는 그대로. 배경 `bg-surface-pearl`.
  - 타이틀 셀: "위험성평가서(불시, 단발성 작업)" — `text-[28px] font-semibold tracking-[-0.5px]`, 배경 흰색.
- 메타 정보 테이블:
  - 라벨 셀: `bg-surface-pearl text-ink-muted-80 text-[13px] font-medium`
  - 본문 셀: 흰색, ink, 13px
- 본문 12행 테이블:
  - 헤더 행: `bg-surface-pearl`, 13px medium
  - 데이터 행: 짝수 행 `bg-[#fcfcfd]`, 홀수 행 흰색
  - 행 패딩: `px-3 py-3` (현행보다 살짝 여유)
- 서명 푸터:
  - 셀 사이 헤어라인, ■ 마커 → 액션 블루 `•` (`<span className="text-primary mr-1">•</span>`)
- 컬럼 너비: 현행 유지 (`w-8 / w-24 / w-28 / fill / fill / w-16`)
- **하드캡 12행 그대로**, `displayRows` 로직 그대로.

이 변경은 **시각만 바꾸고 row 구조·필드명은 동일**해서 백엔드 `rows` 데이터 구조에 영향이 없다.

## 인터랙션 상태

- **입력 focus**: 위에서 정의한 보더 + ring 2px.
- **버튼 loading**: 위 `<PillButton>` 명세. 너비는 `min-w-[140px]` 유지해 흔들리지 않도록.
- **에러 박스**: `rounded-[11px] border border-hairline bg-[#fef2f2] px-4 py-3 text-[14px] text-ink-muted-80`, 좌측에 `⚠️` 1자.
- **다운로드 disabled**: `resp == null || loading || downloading` 그대로.
- **sticky action bar**: 스크롤과 무관하게 항상 보임. 모바일 키보드 올라올 때 가려질 수 있어 `pb-[env(safe-area-inset-bottom)]` 처리.

## 토큰 → Tailwind v4 매핑

`web/src/app/globals.css`의 `@theme inline` 블록에 추가:

```css
@theme inline {
  --color-canvas: #ffffff;
  --color-canvas-parchment: #f5f5f7;
  --color-surface-pearl: #fafafc;
  --color-ink: #1d1d1f;
  --color-ink-muted-80: #333333;
  --color-ink-muted-48: #7a7a7a;
  --color-hairline: #e0e0e0;
  --color-divider-soft: #f0f0f0;
  --color-primary: #0066cc;
  --color-primary-focus: #0071e3;
  --color-on-primary: #ffffff;

  --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif;

  --radius-md: 11px;
  --radius-lg: 18px;
}
```

기존 `--font-geist-sans/mono`, 다크모드 미디어쿼리는 삭제. body의 `font-family: Arial, ...` → `font-sans` 이용.

`layout.tsx`의 `next/font/google` Geist import 삭제. body class에서 폰트 토큰 사용. `metadata`의 "Create Next App" → 한국어 타이틀로 교체("AI 위험성평가 도우미").

## 파일 변경 범위

| 파일 | 변경 |
|---|---|
| `web/src/app/globals.css` | `@theme` 토큰 추가, 다크모드 블록 삭제, body 폰트 교체 |
| `web/src/app/layout.tsx` | Geist 폰트 제거, body class 단순화, metadata 한국어 |
| `web/src/app/page.tsx` | 전면 재작성. 새 컴포넌트(`Card`, `Row`, `TextField`, `SegmentedControl`, `PillButton`, `MetaChip`) 인라인 추가. 폼 4개 카드 그룹화. sticky action bar. 회사 양식 미리보기 재스타일. 기존 `Field`/`MetaLabel` 제거. |

**새 파일 없음. 백엔드(`webapp/backend/`), Excel 템플릿, 인제스트, 테스트 미수정.**

기능 동작은 동등:
- `toRequest(form)` 동일
- `runAssess` / `download` 동일
- 상태(`form`, `loading`, `downloading`, `error`, `resp`) 동일
- `displayRows`로 12행 패딩 동일

## 테스트

`web/`에 별도 단위 테스트 인프라가 없다(README/lint만 존재). 검증은 다음으로 한다:

1. `npm run lint` 통과 (eslint flat config).
2. `npm run build` 통과 (Next.js 16 prerelease, 타입 체크 포함).
3. `npm run dev`로 띄워 브라우저에서 시각 점검:
   - 폼 4개 카드 그룹이 보이고, 모든 16개 필드가 보존되었는지
   - segmented control이 사고 강도 4단계로 동작하는지
   - 생성 버튼 로딩 spinner, 에러 박스, 다운로드 disabled
   - 결과 영역의 회사 양식 미리보기가 12행 표시되는지
   - sticky action bar가 스크롤 중에도 하단에 고정되는지
   - 모바일 폭(375px)에서 카드 row가 깨지지 않는지

자동 테스트 추가는 이번 스코프에서 제외(별도 디자인 회귀 인프라가 없는 상황에서 셋업까지 끌고 가면 과한 스코프).

## 위험 & 결정

- **SF Pro 폰트는 시스템 폰트라 웹폰트 로드 없음.** 윈도우/리눅스 사용자는 시스템 산세리프(Segoe UI / Roboto)로 폴백. 의도된 트레이드오프 — 라이선스/로드 비용 없음.
- **회사 양식 미리보기를 애플풍으로 재스타일하면 다운로드 Excel과 시각이 달라진다.** 사용자가 두 번째 질문에서 "양식도 애플풍으로"를 선택. WYSIWYG 정합성보다 일관된 비주얼 우선.
- **Next.js 16 prerelease**: `web/AGENTS.md`에 따라 App Router 패턴은 그대로. 단일 페이지 client component(`"use client"`)이므로 새 API 사용 안 함. 변경은 JSX/CSS 한정이라 prerelease 영향 적음.
- **Tailwind v4 `@theme`**: 신택스 변경 시 의존. 현재 globals.css가 이미 `@theme inline`을 쓰고 있어 위험 낮음.
