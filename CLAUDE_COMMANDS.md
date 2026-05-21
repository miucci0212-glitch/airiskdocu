# Claude Code 명령어 가이드

> Superpowers (v5.0.7) + GStack (Garry Tan) 통합 명령어 정리

---

## Superpowers

Claude Code의 작업 방식을 구조화하는 프로세스 스킬 모음.  
"어떻게 일할 것인가"를 정의한다.

### 개발 워크플로우

| 명령어 | 설명 |
|--------|------|
| `/brainstorming` | 코드 작성 전 반드시 실행. 기능 추가·컴포넌트 생성·동작 수정 등 모든 창작 작업 전에 사용자 의도, 요구사항, 설계를 먼저 탐색한다 |
| `/writing-plans` | 스펙이나 요구사항이 있을 때, 코드 수정 전에 다단계 구현 계획을 수립한다 |
| `/executing-plans` | 작성된 구현 계획을 별도 세션에서 검토 체크포인트와 함께 실행한다 |
| `/subagent-driven-development` | 현재 세션에서 독립적인 태스크들을 병렬로 실행할 때 사용한다 |
| `/dispatching-parallel-agents` | 공유 상태나 순서 의존성 없이 병렬로 처리 가능한 독립적인 태스크 2개 이상이 있을 때 사용한다 |

### 코드 품질

| 명령어 | 설명 |
|--------|------|
| `/test-driven-development` | 기능 구현이나 버그 수정 전, 구현 코드 작성 전에 반드시 실행. TDD 방식으로 접근한다 |
| `/systematic-debugging` | 버그·테스트 실패·예상치 못한 동작 발생 시, 수정 제안 전에 실행. 체계적으로 근본 원인을 파악한다 |
| `/verification-before-completion` | 작업 완료·수정 완료·테스트 통과를 선언하기 전에 실행. 커밋이나 PR 생성 전에 검증 명령을 실제로 실행하고 결과를 확인한다 |
| `/requesting-code-review` | 태스크 완료·주요 기능 구현·병합 전에 작업이 요구사항을 충족하는지 검증한다 |
| `/receiving-code-review` | 코드 리뷰 피드백을 받았을 때, 제안 구현 전에 실행. 기술적 엄밀성을 요구하며 무조건적 동의나 맹목적 구현을 방지한다 |

### Git & 배포

| 명령어 | 설명 |
|--------|------|
| `/using-git-worktrees` | 현재 작업 공간과 격리가 필요한 기능 작업 시작 시 또는 구현 계획 실행 전에 사용. 안전 검증과 함께 격리된 git worktree를 생성한다 |
| `/finishing-a-development-branch` | 구현 완료·테스트 통과 후 작업 통합 방법을 결정할 때 사용. merge·PR·정리 등의 구조화된 옵션을 제시한다 |

### 스킬 관리

| 명령어 | 설명 |
|--------|------|
| `/writing-skills` | 새 스킬 생성·기존 스킬 편집·스킬 배포 전 검증 시 사용한다 |
| `/using-superpowers` | 대화 시작 시 자동 실행. 스킬 사용 방법을 확립하고, 모든 응답(명확화 질문 포함) 전에 Skill 도구 호출을 요구한다 |

---

## GStack

Garry Tan(Y Combinator CEO)의 Claude Code 스킬셋.  
"Think → Plan → Build → Review → Test → Ship → Reflect" 스프린트 사이클을 구현한다.

### 1단계: 기획 (Think & Plan)

| 명령어 | 담당 역할 | 설명 |
|--------|-----------|------|
| `/office-hours` | YC Office Hours | **여기서 시작.** 6가지 핵심 질문으로 제품을 재정의한다. 프레이밍에 반박하고, 전제를 검증하고, 구현 대안을 제시한다. 작성된 설계 문서는 이후 모든 스킬에 자동으로 전달된다 |
| `/plan-ceo-review` | CEO / 창업자 | 문제를 다시 생각한다. 요청 안에 숨겨진 10성급 제품을 찾는다. 4가지 모드: 확장·선택적 확장·범위 유지·축소 |
| `/plan-eng-review` | 엔지니어링 매니저 | 아키텍처·데이터 흐름·다이어그램·엣지 케이스·테스트를 확정한다. 숨겨진 가정들을 표면화한다 |
| `/plan-design-review` | 시니어 디자이너 | 각 디자인 차원을 0-10점으로 평가하고 10점 기준을 설명한 후 계획을 수정한다. AI Slop 감지 포함. 각 디자인 결정마다 한 번씩 상호작용한다 |
| `/plan-devex-review` | 개발자 경험 리드 | DX 인터랙티브 리뷰: 개발자 페르소나 탐색, 경쟁사 TTHW 벤치마크, 마법 같은 첫 경험 설계. 20-45개 핵심 질문. 3가지 모드: DX EXPANSION·DX POLISH·DX TRIAGE |
| `/autoplan` | 리뷰 파이프라인 | 원 커맨드 완전 검토 계획. CEO → 디자인 → 엔지니어링 리뷰를 자동으로 실행하고 취향 결정 사항만 승인을 요청한다 |

### 2단계: 디자인 (Design)

| 명령어 | 담당 역할 | 설명 |
|--------|-----------|------|
| `/design-consultation` | 디자인 파트너 | 완전한 디자인 시스템을 처음부터 구축한다. 시장 조사, 창의적 리스크 제안, 현실적인 제품 목업 생성 |
| `/design-shotgun` | 디자인 탐색가 | "옵션을 보여줘." 4-6가지 AI 목업 변형을 생성하고 브라우저에서 비교판을 열고 피드백을 수집·반복한다. 취향 메모리가 선호도를 학습한다. 마음에 들면 `/design-html`로 전달 |
| `/design-html` | 디자인 엔지니어 | 목업을 실제로 작동하는 프로덕션 HTML로 변환한다. 텍스트 리플로우, 동적 레이아웃, 30KB 제로 의존성. React/Svelte/Vue 자동 감지 |
| `/design-review` | 코딩하는 디자이너 | `/plan-design-review`와 동일한 감사 후 발견한 문제를 직접 수정한다. 원자적 커밋, 전후 스크린샷 |

### 3단계: 빌드 후 검토 (Review)

| 명령어 | 담당 역할 | 설명 |
|--------|-----------|------|
| `/review` | 스태프 엔지니어 | CI는 통과하지만 프로덕션에서 터지는 버그를 찾는다. 명백한 것들은 자동 수정. 완성도 부족 부분을 표시 |
| `/investigate` | 디버거 | 체계적인 근본 원인 분석. 철칙: 조사 없이 수정 없음. 데이터 흐름 추적, 가설 검증, 3회 실패 시 중단 |
| `/devex-review` | DX 테스터 | 실시간 개발자 경험 감사. 실제로 온보딩을 테스트: 문서 탐색, 시작 플로우 실행, TTHW 측정, 오류 스크린샷. `/plan-devex-review` 점수와 비교해 계획 대 현실 검증 |
| `/cso` | 최고 보안 책임자 | OWASP Top 10 + STRIDE 위협 모델. 제로 노이즈: 17개 오탐 제외, 8/10 이상 신뢰도 게이트, 독립적 발견 검증. 각 발견에 구체적 공격 시나리오 포함 |

### 4단계: 테스트 (Test)

| 명령어 | 담당 역할 | 설명 |
|--------|-----------|------|
| `/qa` | QA 리드 | 앱을 테스트하고, 버그를 찾고, 원자적 커밋으로 수정하고, 재검증한다. 모든 수정에 대해 회귀 테스트를 자동 생성 |
| `/qa-only` | QA 리포터 | `/qa`와 동일한 방법론이지만 보고만 한다. 코드 변경 없이 순수 버그 리포트 |
| `/benchmark` | 성능 엔지니어 | 페이지 로드 시간, Core Web Vitals, 리소스 크기를 기준선으로 측정. 모든 PR마다 전후 비교 |
| `/browse` | QA 엔지니어 | 에이전트에게 눈을 준다. 실제 Chromium 브라우저, 실제 클릭, 실제 스크린샷. 명령당 ~100ms |

### 5단계: 배포 (Ship)

| 명령어 | 담당 역할 | 설명 |
|--------|-----------|------|
| `/ship` | 릴리즈 엔지니어 | main 동기화, 테스트 실행, 커버리지 감사, 푸시, PR 생성. 테스트 프레임워크가 없으면 자동으로 부트스트랩 |
| `/land-and-deploy` | 릴리즈 엔지니어 | PR 병합, CI 및 배포 대기, 프로덕션 상태 검증. "승인됨"에서 "프로덕션 검증 완료"까지 원 커맨드 |
| `/canary` | SRE | 배포 후 모니터링 루프. 콘솔 오류, 성능 회귀, 페이지 실패를 감시한다 |
| `/document-release` | 기술 문서 작성자 | 방금 배포한 내용에 맞게 모든 프로젝트 문서를 업데이트한다. 오래된 README를 자동으로 감지 |

### 6단계: 회고 (Reflect)

| 명령어 | 담당 역할 | 설명 |
|--------|-----------|------|
| `/retro` | 엔지니어링 매니저 | 팀 인식 주간 회고. 개인별 분석, 배포 스트릭, 테스트 상태 추이, 성장 기회. `/retro global`은 모든 프로젝트와 AI 도구(Claude Code, Codex, Gemini)를 횡단 분석 |
| `/learn` | 메모리 | gstack이 세션 전반에서 학습한 내용을 관리한다. 프로젝트별 패턴·함정·선호도를 검토·검색·정리·내보내기. 학습이 누적돼 점점 코드베이스에 최적화된다 |

### 파워 툴

| 명령어 | 설명 |
|--------|------|
| `/careful` | 안전 가드레일. 파괴적인 명령(`rm -rf`, `DROP TABLE`, force-push) 전에 경고한다. "be careful"이라고 말하면 활성화. 경고는 언제든 무시 가능 |
| `/freeze` | 편집 잠금. 파일 수정을 특정 디렉토리 하나로 제한한다. 디버깅 중 범위 밖 실수 방지 |
| `/guard` | 완전 안전. `/careful` + `/freeze`를 한 번에. 프로덕션 작업에 최대 안전장치 |
| `/unfreeze` | `/freeze` 경계를 해제한다 |
| `/pair-agent` | 멀티 에이전트 코디네이터. 브라우저를 다른 AI 에이전트와 공유한다. OpenClaw·Hermes·Codex·Cursor 등 curl 가능한 모든 에이전트 지원. 스코프 토큰, 탭 격리, 요청 제한, 활동 귀속 |
| `/open-gstack-browser` | GStack Browser 실행. 사이드바, 안티봇 스텔스, 자동 모델 라우팅(액션은 Sonnet, 분석은 Opus), 원클릭 쿠키 임포트 |
| `/setup-browser-cookies` | 실제 브라우저(Chrome·Arc·Brave·Edge)에서 쿠키를 헤드리스 세션으로 가져온다. 인증된 페이지 테스트 가능 |
| `/setup-deploy` | `/land-and-deploy`를 위한 1회 설정. 플랫폼·프로덕션 URL·배포 명령을 자동 감지 |
| `/setup-gbrain` | GBrain 온보딩. PGLite 로컬·기존 Supabase URL·신규 Supabase 프로비저닝 중 선택 |
| `/codex` | 세컨드 오피니언. OpenAI Codex CLI의 독립적 코드 리뷰. 3가지 모드: 리뷰(pass/fail 게이트)·적대적 도전·오픈 상담 |
| `/gstack-upgrade` | 자가 업데이터. gstack을 최신 버전으로 업그레이드한다. 글로벌·벤더 설치 모두 감지, 변경 사항 표시 |

---

## 추천 워크플로우

### 새 기능 개발

```
/office-hours → /plan-ceo-review → /plan-eng-review → /brainstorming
→ /writing-plans → /test-driven-development → (구현)
→ /review → /cso → /qa → /ship
```

### 버그 수정

```
/systematic-debugging → /investigate → (수정)
→ /verification-before-completion → /ship
```

### 디자인 작업

```
/design-shotgun → /design-html → /design-review → /qa → /ship
```

### 배포 후

```
/canary → /benchmark → /retro → /document-release
```

---

## 설치 경로

| 플러그인 | 경로 |
|----------|------|
| Superpowers | `~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.7/` |
| GStack | `~/.claude/skills/gstack/` |
| GStack Browse 바이너리 | `~/.claude/skills/gstack/browse/dist/browse` |
