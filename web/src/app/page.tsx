"use client";

import { useEffect, useState } from "react";
import { KrcForm } from "./krc-form";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

type AssessRow = {
  location: string;
  work: string;
  hazard: string;
  control: string;
  note: string;
};

type RagSource = { sheet: string; row_id: string; hazard_snippet: string };

type AssessResponse = {
  rows: AssessRow[];
  sources: RagSource[];
  meta: { model: string; thinking_budget: number; fallback_used: boolean };
};

const MODELS = [
  { value: "", label: "자동 (AI 추론 수준에 따라 결정)" },
  { value: "gemini-3.5-flash", label: "Gemini 3.5 Flash (최신·빠름)" },
  { value: "gemini-3.1-pro-preview", label: "Gemini 3.1 Pro Preview (고성능)" },
  { value: "gemini-3.1-flash-lite-preview", label: "Gemini 3.1 Flash-Lite Preview (경량)" },
  { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro (고성능)" },
  { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash (빠름)" },
  { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
];

const THINKING_LEVELS = ["fast", "balanced", "thorough", "max"] as const;
type ThinkingLevel = (typeof THINKING_LEVELS)[number];

const THINKING_LABELS: Record<ThinkingLevel, string> = {
  fast: "속도 우선",
  balanced: "균형",
  thorough: "품질 우선",
  max: "최고 품질",
};

const COMPANIES = ["태영건설", "농어촌공사"] as const;
type Company = (typeof COMPANIES)[number];

type GenerationMode = "db" | "hybrid";

const DEFAULT_REQUEST = {
  site_name: "서면 어반센트 데시앙 신축공사",
  vendor: "㈜한창테크",
  trade: "금속",
  period: { start: "2026-04-28", end: "2026-04-28" },
  headcount: 2,
  leader: "김재한",
  workers_csv: "김영열",
  equipment_csv: "핸드그라인더, 용접기",
  machinery: "해당없음",
  safety_manager: "홍길동",
  supervisor: "홍길동",
  site_manager: "홍길동",
  locations_csv: "현장출입구, 감리실 외부 출입구",
  work_description: "출입구 도어 시공, 몰딩 시공",
  thinking_level: "balanced" as ThinkingLevel,
  model_override: "",
  generation_mode: "hybrid" as GenerationMode,
};

function toRequest(form: typeof DEFAULT_REQUEST) {
  return {
    site_name: form.site_name,
    vendor: form.vendor,
    trade: form.trade,
    period: form.period,
    headcount: Number(form.headcount),
    leader: form.leader,
    workers: form.workers_csv.split(",").map((s) => s.trim()).filter(Boolean),
    equipment: form.equipment_csv.split(",").map((s) => s.trim()).filter(Boolean),
    machinery: form.machinery,
    locations: form.locations_csv.split(",").map((s) => s.trim()).filter(Boolean),
    work_description: form.work_description,
    thinking_level: form.thinking_level,
    model_override: form.model_override || null,
    generation_mode: form.generation_mode,
  };
}

function formatDate(dateStr: string) {
  if (!dateStr) return "";
  const [y, m, d] = dateStr.split("-");
  return `${y}. ${m}. ${d}.`;
}

function formatPeriod(start: string, end: string) {
  if (!start && !end) return "";
  if (start === end) return formatDate(start);
  return `${formatDate(start)} ~ ${formatDate(end)}`;
}

export default function Home() {
  const [company, setCompany] = useState<Company>("농어촌공사");
  const [form, setForm] = useState(DEFAULT_REQUEST);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resp, setResp] = useState<AssessResponse | null>(null);

  const [progress, setProgress] = useState(0);
  useEffect(() => {
    if (!loading) return;
    const startTime = Date.now();
    const id = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const ratio = 1 - Math.exp(-elapsed / 12000);
      setProgress(Math.min(92, Math.round(ratio * 100)));
    }, 150);
    return () => {
      clearInterval(id);
      setProgress(100);
      setTimeout(() => setProgress(0), 400);
    };
  }, [loading]);
  const showLoadingModal = loading || progress > 0;

  const [showSurvey, setShowSurvey] = useState(false);
  const [surveyRating, setSurveyRating] = useState<number | null>(null);
  const [surveyComment, setSurveyComment] = useState("");
  const [surveySubmitting, setSurveySubmitting] = useState(false);

  function update<K extends keyof typeof DEFAULT_REQUEST>(k: K, v: (typeof DEFAULT_REQUEST)[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function isDefaultText(key: Exclude<keyof typeof DEFAULT_REQUEST, "period" | "headcount" | "thinking_level" | "model_override">) {
    return form[key] === DEFAULT_REQUEST[key] && DEFAULT_REQUEST[key] !== "";
  }

  async function runAssess() {
    setProgress(3);
    setLoading(true);
    setError(null);
    setResp(null);
    try {
      const r = await fetch(`${API}/api/assess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toRequest(form)),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      setResp(await r.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function handleDownloadClick() {
    if (!resp) return;
    setShowSurvey(true);
  }

  async function submitSurveyAndDownload() {
    if (surveyRating === null) return;
    setSurveySubmitting(true);
    const gasUrl = process.env.NEXT_PUBLIC_SURVEY_GAS_URL || "";
    if (gasUrl) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);
        await fetch(gasUrl, {
          method: "POST",
          mode: "no-cors",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            rating: surveyRating,
            comment: surveyComment,
            siteName: form.site_name,
            writeDate: form.period.start,
            writer: form.leader,
          }),
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
      } catch (err) {
        console.warn("만족도 조사 구글 전송 중 오류 (다운로드는 진행됨):", err);
      }
    }
    setSurveySubmitting(false);
    setShowSurvey(false);
    download();
  }

  async function download() {
    if (!resp) return;
    setDownloading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request: toRequest(form), rows: resp.rows }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      const rawBlob = await r.blob();
      const blob = new Blob([rawBlob], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `위험성평가서_${form.site_name.replaceAll(" ", "_").slice(0, 20)}_${form.period.start.replaceAll("-", "")}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloading(false);
    }
  }

  const TOTAL_ROWS = 12;
  const displayRows: (AssessRow | null)[] = resp
    ? [...resp.rows, ...Array(Math.max(0, TOTAL_ROWS - resp.rows.length)).fill(null)]
    : [];

  return (
    <div className="min-h-screen bg-canvas-parchment text-ink pb-32">
      <header className="border-b border-hairline bg-canvas">
        <div className="mx-auto max-w-3xl px-4 pt-5 pb-4 sm:px-6">
          <div className="flex items-baseline justify-between px-2 sm:px-0">
            <h1 className="text-[22px] font-semibold tracking-[-0.3px]">AI 위험성평가 도우미</h1>
          </div>
          <div className="mt-3 flex items-center gap-3 px-2 sm:px-0">
            <span className="text-[13px] text-ink-muted-80">회사</span>
            <div className="flex-1">
              <SegmentedControl options={COMPANIES} value={company} onChange={setCompany} />
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        {company === "농어촌공사" ? (
          <KrcForm />
        ) : (
        <div className="space-y-6">
          <Card title="현장 정보">
            <Row label="현장명">
              <TextField value={form.site_name} onChange={(v) => update("site_name", v)} muted={isDefaultText("site_name")} />
            </Row>
            <Row label="업체명">
              <TextField value={form.vendor} onChange={(v) => update("vendor", v)} muted={isDefaultText("vendor")} />
            </Row>
            <Row label="작업 책임자">
              <TextField value={form.leader} onChange={(v) => update("leader", v)} muted={isDefaultText("leader")} />
            </Row>
          </Card>

          <Card title="작업 정보">
            <Row label="작업기간 시작">
              <TextField
                type="date"
                value={form.period.start}
                onChange={(v) => update("period", { ...form.period, start: v })}
                muted={form.period.start === DEFAULT_REQUEST.period.start}
              />
            </Row>
            <Row label="작업기간 종료">
              <TextField
                type="date"
                value={form.period.end}
                onChange={(v) => update("period", { ...form.period, end: v })}
                muted={form.period.end === DEFAULT_REQUEST.period.end}
              />
            </Row>
            <Row label="작업인원">
              <TextField
                type="number"
                min={1}
                value={String(form.headcount)}
                onChange={(v) => update("headcount", Math.max(1, Number(v) || 1))}
                muted={form.headcount === DEFAULT_REQUEST.headcount}
              />
            </Row>
            <Row label="건설기계">
              <TextField
                value={form.machinery}
                onChange={(v) => update("machinery", v)}
                placeholder="종류 및 댓 수"
                muted={isDefaultText("machinery")}
              />
            </Row>
            <Row label="근로자">
              <TextField
                value={form.workers_csv}
                onChange={(v) => update("workers_csv", v)}
                placeholder="쉼표로 구분"
                muted={isDefaultText("workers_csv")}
              />
            </Row>
            <Row label="기계/위험물질">
              <TextField
                value={form.equipment_csv}
                onChange={(v) => update("equipment_csv", v)}
                placeholder="쉼표로 구분"
                muted={isDefaultText("equipment_csv")}
              />
            </Row>
            <Row label="작업장소">
              <TextField
                value={form.locations_csv}
                onChange={(v) => update("locations_csv", v)}
                placeholder="쉼표로 구분"
                muted={isDefaultText("locations_csv")}
              />
            </Row>
            <Row label="공종">
              <TextField value={form.trade} onChange={(v) => update("trade", v)} muted={isDefaultText("trade")} />
            </Row>
            <Row block label="작업내용">
              <textarea
                rows={3}
                className={`w-full resize-none rounded-[11px] border border-hairline bg-canvas px-3 py-2 text-[15px] outline-none focus:border-primary-focus focus:ring-2 focus:ring-primary-focus/25 ${
                  isDefaultText("work_description") ? "text-ink-muted-48" : "text-ink"
                }`}
                value={form.work_description}
                onChange={(e) => update("work_description", e.target.value)}
                onFocus={() => {
                  if (isDefaultText("work_description")) update("work_description", "");
                }}
              />
            </Row>
          </Card>

          <Card title="결재 라인">
            <Row label="안전관리자">
              <TextField
                value={form.safety_manager}
                onChange={(v) => update("safety_manager", v)}
                muted={isDefaultText("safety_manager")}
              />
            </Row>
            <Row label="관리감독자">
              <TextField
                value={form.supervisor}
                onChange={(v) => update("supervisor", v)}
                muted={isDefaultText("supervisor")}
              />
            </Row>
            <Row label="현장소장">
              <TextField
                value={form.site_manager}
                onChange={(v) => update("site_manager", v)}
                muted={isDefaultText("site_manager")}
              />
            </Row>
          </Card>

          <div className="rounded-[11px] border border-hairline bg-surface-pearl px-4 py-3 flex flex-col gap-3">
            <div className="text-[13px] text-ink-muted-80 leading-relaxed">
              위험요인, 안전보건추진계획을 포함한 모든 항목이 태영건설 DB와 AI 분석을 통해 자동으로 작성됩니다.
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-[11px] font-semibold text-ink-muted-48 tracking-wide shrink-0">생성 모드</span>
                <div role="radiogroup" aria-label="생성 모드" className="inline-flex rounded-full border border-hairline bg-white p-0.5 shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
                  <button
                    type="button"
                    role="radio"
                    aria-checked={form.generation_mode === "db"}
                    onClick={() => update("generation_mode", "db")}
                    disabled={loading}
                    title="태영건설 DB 어휘·표현을 그대로 사용"
                    className={`px-3 py-1 text-[12px] font-semibold rounded-full transition-colors ${
                      form.generation_mode === "db"
                        ? "bg-primary text-white"
                        : "text-ink-muted-80 hover:bg-surface-pearl"
                    }`}
                  >
                    태영건설 지식 중심
                  </button>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={form.generation_mode === "hybrid"}
                    onClick={() => update("generation_mode", "hybrid")}
                    disabled={loading}
                    title="DB를 시드로 LLM이 일반 건설지식을 결합해 폭넓게 확장"
                    className={`px-3 py-1 text-[12px] font-semibold rounded-full transition-colors ${
                      form.generation_mode === "hybrid"
                        ? "bg-primary text-white"
                        : "text-ink-muted-80 hover:bg-surface-pearl"
                    }`}
                  >
                    DB+AI 혼합
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-[11px] font-semibold text-ink-muted-48 tracking-wide shrink-0">AI 추론 수준</span>
                <div role="radiogroup" aria-label="AI 추론 수준" className="inline-flex rounded-full border border-hairline bg-white p-0.5 shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
                  {THINKING_LEVELS.map((level) => (
                    <button
                      key={level}
                      type="button"
                      role="radio"
                      aria-checked={form.thinking_level === level}
                      onClick={() => update("thinking_level", level)}
                      disabled={loading}
                      title={
                        level === "fast"
                          ? "Gemini 2.5 Flash — 빠르게 즉답"
                          : level === "balanced"
                          ? "Gemini 2.5 Pro — 속도/품질 균형 (기본값)"
                          : level === "thorough"
                          ? "Gemini 3.1 Pro Preview — 8K 토큰까지 추론, 꼼꼼히"
                          : "Gemini 3.1 Pro Preview — 24K 토큰까지 추론, 가장 깊게"
                      }
                      className={`px-3 py-1 text-[12px] font-semibold rounded-full transition-colors ${
                        form.thinking_level === level
                          ? "bg-primary text-white"
                          : "text-ink-muted-80 hover:bg-surface-pearl"
                      }`}
                    >
                      {THINKING_LABELS[level]}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2 min-w-0 max-w-full">
                <span className="text-[11px] font-semibold text-ink-muted-48 tracking-wide shrink-0">AI 모델</span>
                <select
                  aria-label="AI 모델"
                  value={form.model_override}
                  onChange={(e) => update("model_override", e.target.value)}
                  disabled={loading}
                  className="min-w-0 max-w-full rounded-full border border-hairline bg-white px-3 py-1 text-[12px] font-semibold text-ink outline-none focus:border-primary-focus focus:ring-2 focus:ring-primary-focus/25"
                >
                  {MODELS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-[11px] border border-hairline bg-[#fef2f2] px-4 py-3 text-[14px] text-ink-muted-80">
              <span className="mr-2">⚠️</span>
              <span className="whitespace-pre-wrap">{error}</span>
            </div>
          )}

          {resp && (
            <>
              <div className="flex flex-wrap items-center gap-2 pt-2">
                <MetaChip>모델: {resp.meta.model}</MetaChip>
                <MetaChip>thinking budget: {resp.meta.thinking_budget}</MetaChip>
                {resp.meta.fallback_used && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-[12px] text-amber-800">
                    ⚠ LLM 폴백 (RAG 원문)
                  </span>
                )}
              </div>

              <div className="overflow-hidden rounded-[18px] border border-hairline bg-canvas shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                <FormPreview form={form} displayRows={displayRows} />
              </div>

              {resp.sources.length > 0 && (
                <details className="rounded-[11px] border border-hairline bg-canvas px-4 py-3 text-[14px] text-ink-muted-80">
                  <summary className="cursor-pointer font-medium text-ink">
                    RAG 출처 ({resp.sources.length}건)
                  </summary>
                  <ul className="mt-2 space-y-1.5">
                    {resp.sources.map((s, i) => (
                      <li
                        key={i}
                        className="border-t border-divider-soft pt-1.5 first:border-t-0 first:pt-0"
                      >
                        <code className="text-[12px] text-ink-muted-48">{s.sheet}</code> · {s.hazard_snippet}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </div>
        )}
      </main>

      {company === "태영건설" && (
        <div className="fixed inset-x-0 bottom-0 border-t border-hairline bg-white/80 backdrop-blur-md">
          <div
            className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3 sm:px-6"
            style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
          >
            <PillButton
              variant="primary"
              onClick={runAssess}
              loading={loading}
              disabled={loading}
            >
              위험성평가 생성
            </PillButton>
            <PillButton
              variant="secondary"
              onClick={handleDownloadClick}
              loading={downloading}
              disabled={!resp || loading || downloading}
            >
              엑셀 다운로드
            </PillButton>
          </div>
        </div>
      )}

      {company === "태영건설" && showLoadingModal && (
        <div className="fixed inset-0 z-[9000] flex items-center justify-center p-4 animate-fade-in bg-[#000]/45">
          <div className="bg-white/95 backdrop-blur-md rounded-[24px] border border-hairline p-8 max-w-sm w-full shadow-[0_20px_50px_rgba(0,0,0,0.25)] flex flex-col gap-6 text-center animate-scale-up">
            <div>
              <div className="text-[32px] mb-2">🤖</div>
              <h3 className="text-[18px] font-extrabold tracking-[-0.5px] text-ink">
                위험성평가 생성 중
              </h3>
              <p className="text-[12px] text-ink-muted-48 mt-1.5 leading-relaxed">
                태영건설 DB 검색 + AI 분석을<br />
                진행하고 있습니다
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <div className="h-3 w-full rounded-full bg-[#e8e8ed] overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="text-[14px] font-semibold text-primary tabular-nums">
                {progress}%
              </div>
            </div>
            <p className="text-[11px] text-ink-muted-48 leading-relaxed">
              평균 20~30초 소요됩니다. 잠시만 기다려주세요.
            </p>
          </div>
        </div>
      )}

      {company === "태영건설" && showSurvey && (
        <div className="fixed inset-0 bg-[#000]/65 backdrop-blur-[8px] z-[9999] flex items-center justify-center p-3 sm:p-4 animate-fade-in overflow-y-auto">
          <div
            className="bg-white rounded-[20px] sm:rounded-[24px] border border-hairline p-5 sm:p-7 max-w-md w-full shadow-[0_20px_50px_rgba(0,0,0,0.2)] flex flex-col gap-4 sm:gap-6 text-center animate-scale-up my-auto max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-2rem)] overflow-y-auto"
            style={{ paddingBottom: "max(1.25rem, env(safe-area-inset-bottom))" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <div className="text-[26px] sm:text-[28px] mb-1.5 sm:mb-2 animate-bounce">🌟</div>
              <h3 className="text-[17px] sm:text-[19px] font-extrabold tracking-[-0.5px] text-ink">
                서비스가 만족스러우셨나요?
              </h3>
              <p className="text-[12px] sm:text-[13px] text-ink-muted-48 mt-1.5 leading-relaxed">
                태영건설 위험성평가 도우미 서비스 개선을 위해<br />
                짧은 만족도 한 마디를 부탁드립니다!
              </p>
            </div>
            <div className="grid grid-cols-5 gap-1.5 sm:gap-2.5 my-1">
              {[
                { val: 1, label: "아쉬움", emoji: "😡" },
                { val: 2, label: "그저끎", emoji: "😟" },
                { val: 3, label: "보통", emoji: "😐" },
                { val: 4, label: "만족", emoji: "🙂" },
                { val: 5, label: "매우만족", emoji: "😍" },
              ].map((item) => (
                <button
                  key={item.val}
                  type="button"
                  onClick={() => setSurveyRating(item.val)}
                  className={`flex flex-col items-center justify-center py-2 px-0.5 sm:py-2.5 sm:px-1 rounded-[12px] sm:rounded-[16px] border transition-all duration-200 active:scale-95 min-w-0 ${
                    surveyRating === item.val
                      ? "border-primary bg-primary/5 text-primary scale-105 shadow-[0_4px_12px_rgba(var(--primary-rgb),0.12)]"
                      : "border-hairline hover:border-ink-muted-48 hover:bg-surface-pearl text-ink-muted-80"
                  }`}
                >
                  <span className="text-[20px] sm:text-[24px] mb-1 sm:mb-1.5 select-none leading-none">{item.emoji}</span>
                  <span className="text-[9px] sm:text-[10px] font-semibold leading-tight whitespace-nowrap">{item.label}</span>
                </button>
              ))}
            </div>
            <div className="flex flex-col gap-1.5 text-left">
              <label className="text-[11px] font-bold text-ink-muted-48 uppercase tracking-wider ml-1">의견 또는 건의사항 (선택)</label>
              <textarea
                value={surveyComment}
                onChange={(e) => setSurveyComment(e.target.value)}
                maxLength={200}
                className="w-full rounded-[14px] border border-hairline bg-canvas p-3 outline-none focus:border-primary-focus focus:ring-1 focus:ring-primary-focus h-20 resize-none leading-relaxed text-[13px]"
                placeholder="도움이 된 점이나 아쉬웠던 점을 적어주시면 서비스 개선에 큰 힘이 됩니다."
              />
            </div>
            <div className="flex flex-col gap-2 pt-1">
              <button
                type="button"
                disabled={surveyRating === null || surveySubmitting}
                onClick={submitSurveyAndDownload}
                className={`w-full py-3 rounded-full text-[14px] sm:text-[15px] font-semibold transition-all duration-200 shadow-[0_2px_8px_rgba(0,0,0,0.05)] ${
                  surveyRating !== null
                    ? "bg-primary hover:bg-primary-focus text-on-primary hover:shadow-[0_4px_12px_rgba(var(--primary-rgb),0.2)] active:scale-[0.98]"
                    : "bg-[#e8e8ed] text-ink-muted-48 cursor-not-allowed"
                }`}
              >
                {surveySubmitting ? "만족도 제출 중..." : "만족도 제출 및 엑셀 다운로드"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[18px] border border-hairline bg-canvas">
      <h2 className="px-5 pt-4 pb-2 text-[13px] font-semibold tracking-[-0.2px] text-ink-muted-80">
        {title}
      </h2>
      <div className="divide-y divide-divider-soft">{children}</div>
    </section>
  );
}

function Row({
  label,
  children,
  block,
}: {
  label: string;
  children: React.ReactNode;
  block?: boolean;
}) {
  if (block) {
    return (
      <div className="px-5 py-3">
        <div className="mb-1.5 text-[14px] text-ink-muted-80">{label}</div>
        {children}
      </div>
    );
  }
  return (
    <div className="flex items-center gap-4 px-5 py-3">
      <div className="w-32 shrink-0 text-[14px] text-ink-muted-80">{label}</div>
      <div className="flex-1">{children}</div>
    </div>
  );
}

function TextField({
  value,
  onChange,
  type = "text",
  placeholder,
  min,
  muted,
}: {
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  min?: number;
  muted?: boolean;
}) {
  return (
    <input
      type={type}
      min={min}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      onFocus={() => {
        if (muted && type !== "number") onChange("");
      }}
      className={`w-full rounded-[11px] border border-hairline bg-canvas px-3 py-2 text-[15px] outline-none focus:border-primary-focus focus:ring-2 focus:ring-primary-focus/25 ${
        muted ? "text-ink-muted-48" : "text-ink"
      }`}
    />
  );
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex rounded-[11px] bg-[#e8e8ed] p-1">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={`flex-1 rounded-[8px] py-1.5 text-[13px] transition-colors ${
            value === opt
              ? "bg-canvas font-medium text-ink shadow-[0_1px_2px_rgba(0,0,0,0.06)]"
              : "text-ink-muted-80 hover:text-ink"
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

function PillButton({
  variant,
  loading,
  disabled,
  onClick,
  children,
}: {
  variant: "primary" | "secondary";
  loading?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  const base =
    "inline-flex min-w-[140px] items-center justify-center gap-2 rounded-full px-6 py-2.5 text-[15px] font-medium transition-colors";
  const variantClass =
    variant === "primary"
      ? "bg-primary text-on-primary hover:bg-primary-focus"
      : "bg-canvas text-primary border border-hairline hover:bg-surface-pearl";
  const disabledClass = disabled ? "cursor-not-allowed opacity-40" : "";
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${variantClass} ${disabledClass}`}
    >
      {loading && <Spinner />}
      <span className={loading ? "opacity-60" : ""}>{children}</span>
    </button>
  );
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="2"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" />
      <path className="opacity-75" d="M4 12a8 8 0 018-8" strokeLinecap="round" />
    </svg>
  );
}

function MetaChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-[12px] text-on-primary">
      {children}
    </span>
  );
}

function FormPreview({
  form,
  displayRows,
}: {
  form: typeof DEFAULT_REQUEST;
  displayRows: (AssessRow | null)[];
}) {
  return (
    <div>
      <table className="w-full border-collapse">
        <tbody>
          <tr>
            <td className="w-36 border-b border-hairline bg-surface-pearl px-4 py-3 align-middle">
              <div className="text-center">
                <div className="text-lg font-black leading-tight text-primary">TAEYOUNG</div>
                <div className="text-sm font-semibold text-ink-muted-80">태영건설</div>
              </div>
            </td>
            <td className="border-b border-l border-hairline px-4 py-5 text-center">
              <span className="text-[24px] font-semibold tracking-[-0.5px]">
                위험성평가서(불시, 단발성 작업)
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <table className="w-full border-collapse text-[13px]">
        <tbody>
          <tr>
            <MetaLabel>현 장 명</MetaLabel>
            <td colSpan={3} className="border-b border-l border-hairline px-3 py-2">
              {form.site_name}
            </td>
            <MetaLabel>업체명/공종</MetaLabel>
            <td className="border-b border-l border-hairline px-3 py-2">
              {form.vendor} / {form.trade}
            </td>
            <MetaLabel>작업기간</MetaLabel>
            <td className="border-b border-l border-hairline px-3 py-2">
              {formatPeriod(form.period.start, form.period.end)}
            </td>
          </tr>
          <tr>
            <MetaLabel>작업인원</MetaLabel>
            <td colSpan={3} className="border-b border-l border-hairline px-3 py-2">
              {form.headcount}명
            </td>
            <MetaLabel colSpan={2}>건설기계 종류 및 댓 수</MetaLabel>
            <td colSpan={2} className="border-b border-l border-hairline px-3 py-2">
              {form.machinery}
            </td>
          </tr>
          <tr>
            <MetaLabel>작업 책임자/근로자</MetaLabel>
            <td colSpan={3} className="border-b border-l border-hairline px-3 py-2">
              {form.leader} / {form.workers_csv}
            </td>
            <MetaLabel colSpan={2}>기계/기구 및 위험물질</MetaLabel>
            <td colSpan={2} className="border-b border-l border-hairline px-3 py-2">
              {form.equipment_csv}
            </td>
          </tr>
        </tbody>
      </table>

      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="bg-surface-pearl">
            <th className="w-8 border-b border-hairline px-2 py-2 text-center text-ink-muted-80"></th>
            <th className="w-24 border-b border-l border-hairline px-3 py-2 text-center font-medium text-ink-muted-80">
              작업장소
            </th>
            <th className="w-28 border-b border-l border-hairline px-3 py-2 text-center font-medium text-ink-muted-80">
              작업내용
            </th>
            <th className="border-b border-l border-hairline px-3 py-2 text-center font-medium text-ink-muted-80">
              위험요인
            </th>
            <th className="border-b border-l border-hairline px-3 py-2 text-center font-medium text-ink-muted-80">
              안전보건추진계획
            </th>
            <th className="w-16 border-b border-l border-hairline px-3 py-2 text-center font-medium text-ink-muted-80">
              비 고
            </th>
          </tr>
        </thead>
        <tbody>
          {displayRows.map((row, i) => (
            <tr key={i} className={`align-top ${i % 2 === 1 ? "bg-[#fcfcfd]" : "bg-canvas"}`}>
              <td className="border-b border-hairline px-2 py-3 text-center text-ink-muted-48">
                {i + 1}
              </td>
              <td className="border-b border-l border-hairline px-3 py-3 text-center">
                {row?.location ?? ""}
              </td>
              <td className="border-b border-l border-hairline px-3 py-3 text-center">
                {row?.work ?? ""}
              </td>
              <td className="whitespace-pre-wrap border-b border-l border-hairline px-3 py-3 leading-relaxed">
                {row?.hazard ?? ""}
              </td>
              <td className="whitespace-pre-wrap border-b border-l border-hairline px-3 py-3 leading-relaxed">
                {row?.control ?? ""}
              </td>
              <td className="border-b border-l border-hairline px-3 py-3">{row?.note ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <table className="w-full border-collapse text-[13px]">
        <tbody>
          <tr>
            <td className="px-3 py-3 text-center">
              <span className="text-primary">●</span>{" "}
              <span className="font-medium">작성자(작업 책임자)</span> : {form.leader}
            </td>
            <td className="border-l border-hairline px-3 py-3 text-center">
              <span className="text-primary">●</span> <span className="font-medium">근로자</span> :{" "}
              {form.workers_csv}
            </td>
            <td className="border-l border-hairline px-3 py-3 text-center">
              <span className="text-primary">●</span> <span className="font-medium">안전관리자</span> :{" "}
              {form.safety_manager}
            </td>
            <td className="border-l border-hairline px-3 py-3 text-center">
              <span className="text-primary">●</span> <span className="font-medium">관리감독자</span> :{" "}
              {form.supervisor}
            </td>
            <td className="border-l border-hairline px-3 py-3 text-center">
              <span className="text-primary">●</span> <span className="font-medium">현장소장</span> :{" "}
              {form.site_manager}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function MetaLabel({ children, colSpan }: { children: React.ReactNode; colSpan?: number }) {
  return (
    <td
      colSpan={colSpan}
      className="w-32 whitespace-nowrap border-b border-l border-hairline bg-surface-pearl px-3 py-2 text-center font-medium text-ink-muted-80 first:border-l-0"
    >
      {children}
    </td>
  );
}
