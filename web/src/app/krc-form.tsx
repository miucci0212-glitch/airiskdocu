"use client";

import { Fragment, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

const KRC_TYPES = ["최초/정기", "수시"] as const;
type KrcType = (typeof KRC_TYPES)[number];

type KrcItem = {
  id: string;
  detail_work: string;
  work_location: string;
  equipment: string;
};

type KrcHit = {
  no: number;
  project: string;
  work: string;
  unit_work: string;
  sub_work: string;
  hazard: string;
  accident: string;
  controls: string;
  laws: string;
  permit: string;
  distance: number;
};

type KrcRow = {
  detail_work: string;
  work_location: string;
  equipment: string;
  hazard: string;
  accident_type: string;
  frequency: number | null;
  severity: number | null;
  risk_grade: string;
  controls: string;
  improved_risk: string;
  improvement_due: string;
  executor: string;
  verifier: string;
};

type KrcAssessResponse = { rows: KrcRow[]; sources: KrcHit[] };

type GenerationMode = "db" | "hybrid";

const MAX_ENTRIES = 3;

const DEFAULTS = {
  siteName: "00지구 수리시설개보수사업 토목공사",
  writer: "김재한",
  approverConstruction: "김재한",
  approverSafety: "홍길동",
  approverSiteManager: "홍길동",
  inspectorSupervisor: "홍길동",
} as const;

function todayISO(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addDays(iso: string, days: number): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function emptyItem(): KrcItem {
  return {
    id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Math.random()),
    detail_work: "",
    work_location: "",
    equipment: "",
  };
}

function defaultItems(): KrcItem[] {
  return [
    {
      id: "default-1",
      detail_work: "출입구 도어 시공 및 고정 작업",
      work_location: "현장출입구",
      equipment: "핸드그라인더, 고속절단기, 수공구",
    },
    {
      id: "default-2",
      detail_work: "출입구 도어 주위 코킹(실란트) 마감",
      work_location: "현장출입구 및 외부 감리실",
      equipment: "코킹건, 사다리, 실란트",
    },
  ];
}

function toNum(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function computeRiskGrade(frequency: number | null, severity: number | null): string {
  if (frequency === null || severity === null) return "";
  const score = frequency * severity;
  return score >= 6 ? "상" : score >= 3 ? "중" : "하";
}

function withRiskGrades(rows: KrcRow[]): KrcRow[] {
  return rows.map((r) => {
    const freq = toNum(r.frequency);
    const sev = toNum(r.severity);
    const grade = r.risk_grade && r.risk_grade.trim()
      ? r.risk_grade
      : computeRiskGrade(freq, sev);
    return { ...r, frequency: freq, severity: sev, risk_grade: grade };
  });
}

function defaultRows(): KrcRow[] {
  const items = defaultItems();
  const arr: KrcRow[] = [];
  items.forEach((it) => {
    for (let k = 0; k < 3; k++) {
      arr.push({
        detail_work: it.detail_work,
        work_location: it.work_location,
        equipment: it.equipment,
        hazard: "",
        accident_type: "",
        frequency: null,
        severity: null,
        risk_grade: "",
        controls: "",
        improved_risk: "",
        improvement_due: "",
        executor: "",
        verifier: "",
      });
    }
  });
  return arr;
}

export function KrcForm() {
  const [krcType, setKrcType] = useState<KrcType>("최초/정기");
  const [siteName, setSiteName] = useState<string>(DEFAULTS.siteName);
  const [writeDate, setWriteDate] = useState<string>(todayISO);
  const [writer, setWriter] = useState<string>(DEFAULTS.writer);
  const [periodStart, setPeriodStart] = useState<string>(todayISO);
  const [periodEnd, setPeriodEnd] = useState<string>(() => addDays(todayISO(), 29));

  const [approverConstruction, setApproverConstruction] = useState<string>(DEFAULTS.approverConstruction);
  const [approverSafety, setApproverSafety] = useState<string>(DEFAULTS.approverSafety);
  const [approverSiteManager, setApproverSiteManager] = useState<string>(DEFAULTS.approverSiteManager);
  const [inspectorSupervisor, setInspectorSupervisor] = useState<string>(DEFAULTS.inspectorSupervisor);

  const [items, setItems] = useState<KrcItem[]>(defaultItems);
  const [generationMode, setGenerationMode] = useState<GenerationMode>("hybrid");

  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<KrcRow[] | null>(null);
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

  // 만족도 조사 상태 변수 추가
  const [showSurvey, setShowSurvey] = useState(false);
  const [surveyRating, setSurveyRating] = useState<number | null>(null);
  const [surveyComment, setSurveyComment] = useState("");
  const [surveySubmitting, setSurveySubmitting] = useState(false);

  const filledItems = items.filter(
    (it) => it.detail_work.trim() || it.work_location.trim() || it.equipment.trim(),
  );
  const canSubmit = filledItems.length > 0 && !loading;
  const overCap = filledItems.length > MAX_ENTRIES;

  function metadataPayload() {
    return {
      krc_type: krcType,
      site_name: siteName,
      write_date: writeDate,
      writer,
      period_start: periodStart,
      period_end: periodEnd,
      approver_construction: approverConstruction,
      approver_safety: approverSafety,
      approver_site_manager: approverSiteManager,
      inspector_supervisor: inspectorSupervisor,
    };
  }

  function updateItem(id: string, patch: Partial<KrcItem>) {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  }
  function addItem() {
    setItems((prev) => [...prev, emptyItem()]);
  }
  function removeItem(id: string) {
    setItems((prev) => (prev.length <= 1 ? prev : prev.filter((it) => it.id !== id)));
  }

  function updateRowField(index: number, field: keyof KrcRow, value: KrcRow[keyof KrcRow]) {
    if (!rows) return;
    const newRows = [...rows];
    newRows[index] = { ...newRows[index], [field]: value };
    
    if (field === "frequency" || field === "severity") {
      newRows[index].risk_grade = computeRiskGrade(
        newRows[index].frequency,
        newRows[index].severity,
      );
    }
    setRows(newRows);
  }

  async function addRows(count: number) {
    if (!rows) return;
    setProgress(3);
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/krc/expand`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metadata: metadataPayload(),
          items: filledItems.map(({ detail_work, work_location, equipment }) => ({
            detail_work,
            work_location,
            equipment,
          })),
          existing_rows: rows,
          count,
          generation_mode: generationMode,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      const data = (await r.json()) as KrcAssessResponse;
      setRows([...rows, ...withRiskGrades(data.rows)]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function removeRow(index: number) {
    if (!rows) return;
    const newRows = rows.filter((_, idx) => idx !== index);
    setRows(newRows);
  }


  async function runAssess() {
    if (filledItems.length === 0) return;
    setProgress(3);
    setLoading(true);
    setError(null);
    setRows(null);
    try {
      const r = await fetch(`${API}/api/krc/assess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metadata: metadataPayload(),
          items: filledItems.map(({ detail_work, work_location, equipment }) => ({
            detail_work,
            work_location,
            equipment,
          })),
          generation_mode: generationMode,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      const data = (await r.json()) as KrcAssessResponse;
      setRows(withRiskGrades(data.rows));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function runDownload() {
    if (!rows) return;
    setDownloading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/krc/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metadata: metadataPayload(), rows }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      const rawBlob = await r.blob();
      const blob = new Blob([rawBlob], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const suffix = krcType === "최초/정기" ? "최초정기" : "수시";
      const safeSite = (siteName || "현장").replaceAll(" ", "_").slice(0, 20);
      const dateStr = writeDate.replaceAll("-", "");
      a.href = url;
      a.download = `위험성평가서_${suffix}_${safeSite}_${dateStr}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloading(false);
    }
  }

  // 엑셀 다운로드 클릭 핸들러 (만족도 모달 노출)
  function handleDownloadClick() {
    if (!rows) return;
    setShowSurvey(true);
  }

  // 만족도 설문 제출 및 최종 다운로드 흐름
  async function submitSurveyAndDownload() {
    if (surveyRating === null) return;
    setSurveySubmitting(true);
    
    // 구글 앱스 스크립트 웹앱 주소 (.env.local 우선 적용, 없으면 기본/예시 주소)
    const gasUrl = process.env.NEXT_PUBLIC_SURVEY_GAS_URL || "";
    
    if (gasUrl) {
      try {
        // 타임아웃을 걸어 구글 서버 지연으로 인해 사용자 엑셀 다운로드가 무한 대기하는 문제 방지
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000); // 4초 타임아웃

        await fetch(gasUrl, {
          method: "POST",
          mode: "no-cors", // 구글 앱스 스크립트 특유의 CORS 리다이렉트 대응
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            rating: surveyRating,
            comment: surveyComment,
            siteName: siteName,
            writeDate: writeDate,
            writer: writer,
          }),
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
      } catch (err) {
        console.warn("만족도 조사 구글 전송 중 오류 발생 (다운로드는 무관하게 진행됨):", err);
      }
    } else {
      console.info("만족도 조사 주소(NEXT_PUBLIC_SURVEY_GAS_URL)가 빈 값입니다. 다운로드만 바로 진행합니다.");
    }
    
    setSurveySubmitting(false);
    setShowSurvey(false);
    
    // 설문이 끝나면 실제 엑셀 다운로드 실행
    runDownload();
  }

  return (
    <div className="space-y-6">
      <Card title="양식 유형">
        <Row label="평가 유형">
          <Segmented options={KRC_TYPES} value={krcType} onChange={setKrcType} />
        </Row>
      </Card>

      <Card title="기본 정보">
        <Row label="현장명">
          <Text
            value={siteName}
            onChange={setSiteName}
            placeholder="예: 서면 어반센트 데시앙 신축공사"
            muted={siteName === DEFAULTS.siteName}
          />
        </Row>
        <Row label="작성일">
          <Text type="date" value={writeDate} onChange={setWriteDate} />
        </Row>
        <Row label="작성자">
          <Text
            value={writer}
            onChange={setWriter}
            placeholder="위험성평가서 작성자"
            muted={writer === DEFAULTS.writer}
          />
        </Row>
        <Row label="관리기간 시작일">
          <Text type="date" value={periodStart} onChange={setPeriodStart} />
        </Row>
        <Row label="관리기간 종료일">
          <div className="flex flex-col gap-2">
            <Text type="date" value={periodEnd} onChange={setPeriodEnd} />
            <div className="flex gap-2">
              <PresetChip
                label="7일"
                onClick={() => setPeriodEnd(addDays(periodStart, 6))}
                disabled={!periodStart}
              />
              <PresetChip
                label="30일"
                onClick={() => setPeriodEnd(addDays(periodStart, 29))}
                disabled={!periodStart}
              />
            </div>
          </div>
        </Row>
      </Card>

      <Card title="결재 / 점검">
        <Row label="공사 (작성자)">
          <Text
            value={approverConstruction}
            onChange={setApproverConstruction}
            muted={approverConstruction === DEFAULTS.approverConstruction}
          />
        </Row>
        <Row label="안전">
          <Text
            value={approverSafety}
            onChange={setApproverSafety}
            muted={approverSafety === DEFAULTS.approverSafety}
          />
        </Row>
        <Row label="현장소장">
          <Text
            value={approverSiteManager}
            onChange={setApproverSiteManager}
            muted={approverSiteManager === DEFAULTS.approverSiteManager}
          />
        </Row>
        <Row label="공사감독 (점검)">
          <Text
            value={inspectorSupervisor}
            onChange={setInspectorSupervisor}
            muted={inspectorSupervisor === DEFAULTS.inspectorSupervisor}
          />
        </Row>
      </Card>

      <section className="space-y-4">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-[15px] font-semibold tracking-[-0.2px] text-ink">
            작업 항목 ({items.length})
          </h2>
          <button
            type="button"
            onClick={addItem}
            className="inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-1.5 text-[13px] font-medium text-on-primary hover:bg-primary-focus"
          >
            + 항목 추가
          </button>
        </div>

        {items.map((it, idx) => (
          <section key={it.id} className="rounded-[18px] border border-hairline bg-canvas">
            <div className="flex items-center justify-between px-5 pt-4 pb-2">
              <h3 className="text-[13px] font-semibold tracking-[-0.2px] text-ink-muted-80">
                항목 {idx + 1}
              </h3>
              <button
                type="button"
                disabled={items.length <= 1}
                onClick={() => removeItem(it.id)}
                className="text-[12px] text-ink-muted-48 hover:text-ink disabled:opacity-30"
              >
                삭제
              </button>
            </div>
            <div className="divide-y divide-divider-soft">
              <Row label="세부작업 (단위작업)">
                <Text
                  value={it.detail_work}
                  onChange={(v) => updateItem(it.id, { detail_work: v })}
                  placeholder="예: 도장 작업"
                />
              </Row>
              <Row label="작업위치">
                <Text
                  value={it.work_location}
                  onChange={(v) => updateItem(it.id, { work_location: v })}
                  placeholder="예: 5층 외벽"
                />
              </Row>
              <Row label="사용장비/설비/인원">
                <Text
                  value={it.equipment}
                  onChange={(v) => updateItem(it.id, { equipment: v })}
                  placeholder="예: 롤러, 사다리, 2명"
                />
              </Row>
            </div>
          </section>
        ))}

        <button
          type="button"
          onClick={addItem}
          className="w-full rounded-[14px] border border-dashed border-hairline bg-transparent py-3 text-[14px] text-ink-muted-80 hover:bg-surface-pearl"
        >
          + 작업 항목 추가
        </button>
      </section>

      {overCap && (
        <div className="rounded-[11px] border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
          ⚠ 농어촌공사 양식은 한 장에 최대 {MAX_ENTRIES}개 항목까지 들어갑니다. 초과분은 엑셀에 포함되지 않습니다.
        </div>
      )}

      <div className="rounded-[11px] border border-hairline bg-surface-pearl px-4 py-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-[13px] text-ink-muted-80 leading-relaxed">
          위험요인, 재해유형, 안전대책 및 위험성 등급을 포함한 모든 항목이 농어촌공사 DB와 AI 분석을 통해 자동으로 작성됩니다.
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[11px] font-semibold text-ink-muted-48 tracking-wide">생성 모드</span>
          <div role="radiogroup" aria-label="생성 모드" className="inline-flex rounded-full border border-hairline bg-white p-0.5 shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
            <button
              type="button"
              role="radio"
              aria-checked={generationMode === "db"}
              onClick={() => setGenerationMode("db")}
              disabled={loading}
              title="농어촌공사 DB 어휘·표현을 그대로 사용"
              className={`px-3 py-1 text-[12px] font-semibold rounded-full transition-colors ${
                generationMode === "db"
                  ? "bg-primary text-white"
                  : "text-ink-muted-80 hover:bg-surface-pearl"
              }`}
            >
              DB 중심
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={generationMode === "hybrid"}
              onClick={() => setGenerationMode("hybrid")}
              disabled={loading}
              title="DB를 시드로 LLM이 일반 건설지식을 결합해 폭넓게 확장"
              className={`px-3 py-1 text-[12px] font-semibold rounded-full transition-colors ${
                generationMode === "hybrid"
                  ? "bg-primary text-white"
                  : "text-ink-muted-80 hover:bg-surface-pearl"
              }`}
            >
              DB+AI 혼합
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-[11px] border border-hairline bg-[#fef2f2] px-4 py-3 text-[14px] text-ink-muted-80">
          <span className="mr-2">⚠️</span>
          <span className="whitespace-pre-wrap">{error}</span>
        </div>
      )}

      {rows && (
        <KrcPreview
          rows={rows}
          onUpdateRow={updateRowField}
          onAddRows={addRows}
          onRemoveRow={removeRow}
          krcType={krcType}
          siteName={siteName}
          writeDate={writeDate}
          writer={writer}
          periodStart={periodStart}
          periodEnd={periodEnd}
          approverConstruction={approverConstruction}
          approverSafety={approverSafety}
          approverSiteManager={approverSiteManager}
          inspectorSupervisor={inspectorSupervisor}
        />
      )}

      <div className="fixed inset-x-0 bottom-0 border-t border-hairline bg-white/80 backdrop-blur-md z-50">
        <div
          className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3 sm:px-6"
          style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
        >
          <div className="flex items-center gap-3">
            <PillButton variant="primary" onClick={runAssess} loading={loading} disabled={!canSubmit}>
              위험성평가 생성
            </PillButton>
            <PillButton
              variant="secondary"
              onClick={handleDownloadClick}
              loading={downloading}
              disabled={!rows || loading || downloading}
            >
              엑셀 다운로드
            </PillButton>
          </div>

          {rows && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => addRows(3)}
                className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 hover:bg-primary/20 px-4 py-2 text-[12px] font-semibold text-primary shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors active:scale-95"
              >
                ➕ 3줄 추가
              </button>
              <button
                type="button"
                onClick={() => addRows(1)}
                className="inline-flex items-center gap-1.5 rounded-full border border-hairline hover:bg-surface-pearl px-4 py-2 text-[12px] font-semibold text-ink shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors active:scale-95"
              >
                ➕ 1줄 추가
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 위험성평가 생성 진행률 모달 */}
      {showLoadingModal && (
        <div className="fixed inset-0 z-[9000] flex items-center justify-center p-4 animate-fade-in bg-[#000]/45">
          <div className="bg-white/95 backdrop-blur-md rounded-[24px] border border-hairline p-8 max-w-sm w-full shadow-[0_20px_50px_rgba(0,0,0,0.25)] flex flex-col gap-6 text-center animate-scale-up">
            <div>
              <div className="text-[32px] mb-2">🤖</div>
              <h3 className="text-[18px] font-extrabold tracking-[-0.5px] text-ink">
                {rows ? "위험요인 추가 생성 중" : "위험성평가 생성 중"}
              </h3>
              <p className="text-[12px] text-ink-muted-48 mt-1.5 leading-relaxed">
                농어촌공사 DB 검색 + AI 분석을<br />
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

      {/* 만족도 설문조사 모달 (Glassmorphism & Interactive design) */}
      {showSurvey && (
        <div className="fixed inset-0 bg-[#000]/65 backdrop-blur-[8px] z-[9999] flex items-center justify-center p-3 sm:p-4 animate-fade-in overflow-y-auto">
          <div
            className="bg-white rounded-[20px] sm:rounded-[24px] border border-hairline p-5 sm:p-7 max-w-md w-full shadow-[0_20px_50px_rgba(0,0,0,0.2)] flex flex-col gap-4 sm:gap-6 text-center animate-scale-up my-auto max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-2rem)] overflow-y-auto"
            style={{ paddingBottom: "max(1.25rem, env(safe-area-inset-bottom))" }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* 모달 상단 */}
            <div>
              <div className="text-[26px] sm:text-[28px] mb-1.5 sm:mb-2 animate-bounce">🌟</div>
              <h3 className="text-[17px] sm:text-[19px] font-extrabold tracking-[-0.5px] text-ink">
                서비스가 만족스러우셨나요?
              </h3>
              <p className="text-[12px] sm:text-[13px] text-ink-muted-48 mt-1.5 leading-relaxed">
                농어촌공사 위험성평가 도우미 서비스 개선을 위해<br />
                짧은 만족도 한 마디를 부탁드립니다!
              </p>
            </div>

            {/* 만족도 등급 이모지 카드 (1~5) */}
            <div className="grid grid-cols-5 gap-1.5 sm:gap-2.5 my-1">
              {[
                { val: 1, label: "아쉬움", emoji: "😡" },
                { val: 2, label: "그저끎", emoji: "😟" },
                { val: 3, label: "보통", emoji: "😐" },
                { val: 4, label: "만족", emoji: "🙂" },
                { val: 5, label: "매우만족", emoji: "😍" }
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

            {/* 한줄 코멘트 / 건의사항 */}
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

            {/* 최종 제출 액션 버튼 */}
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
      <h2 className="px-5 pt-4 pb-2 text-[13px] font-semibold tracking-[-0.2px] text-ink-muted-80">{title}</h2>
      <div className="divide-y divide-divider-soft">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5 px-5 py-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="text-[13px] text-ink-muted-80 sm:w-36 sm:shrink-0 sm:text-[14px]">{label}</div>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

type KrcPreviewProps = {
  rows: KrcRow[];
  onUpdateRow: (index: number, field: keyof KrcRow, value: KrcRow[keyof KrcRow]) => void;
  onAddRows: (count: number) => void;
  onRemoveRow: (index: number) => void;
  krcType: KrcType;
  siteName: string;
  writeDate: string;
  writer: string;
  periodStart: string;
  periodEnd: string;
  approverConstruction: string;
  approverSafety: string;
  approverSiteManager: string;
  inspectorSupervisor: string;
};

function StampBox({ role, name }: { role: string; name: string }) {
  return (
    <div className="flex flex-col items-center justify-center border border-hairline rounded-[8px] bg-canvas p-1.5 w-[64px] h-[76px] shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
      <span className="text-[9px] text-ink-muted-48 border-b border-divider-soft w-full text-center pb-0.5 mb-1 font-semibold">{role}</span>
      <span className="text-[11px] font-bold text-ink-muted-80 truncate max-w-full text-center">{name || "-"}</span>
      {name ? (
        <span className="text-[8px] text-[#cc3333] border border-[#cc3333]/40 rounded-full px-1.5 py-[0.5px] mt-1.5 scale-90 font-bold bg-[#cc3333]/5 tracking-wider">
          인
        </span>
      ) : (
        <span className="text-[8px] text-ink-muted-48/40 border border-hairline rounded-full px-1 py-[0.5px] mt-1.5 scale-90 font-medium">
          미서명
        </span>
      )}
    </div>
  );
}

function formatDate(dateStr: string) {
  if (!dateStr) return "";
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  const [y, m, d] = parts;
  return `${y}. ${m}. ${d}.`;
}

function formatPeriod(start: string, end: string) {
  if (!start && !end) return "";
  if (start === end) return formatDate(start);
  return `${formatDate(start)} ~ ${formatDate(end)}`;
}

function KrcPreview({
  rows,
  onUpdateRow,
  onAddRows,
  onRemoveRow,
  krcType,
  siteName,
  writeDate,
  writer,
  periodStart,
  periodEnd,
  approverConstruction,
  approverSafety,
  approverSiteManager,
  inspectorSupervisor,
}: KrcPreviewProps) {
  const title = krcType === "수시" ? "수시 위험성평가서" : "최초/정기 위험성평가서";
  return (
    <section className="space-y-4 pt-2 pb-6">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-[15px] font-semibold tracking-[-0.2px] text-ink">생성 결과 (실시간 편집 가능)</h2>
        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-[11px] font-medium text-primary shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
          ← 좌우로 스크롤하여 전체 양식을 확인 및 수정하세요 →
        </span>
      </div>

      <div className="overflow-x-auto rounded-[18px] border border-hairline bg-canvas shadow-[0_2px_8px_rgba(0,0,0,0.04)]">
        <div style={{ minWidth: "1300px" }} className="p-1 divide-y divide-hairline">
          {/* Header block with Logo & Title */}
          <table className="w-full border-collapse">
            <tbody>
              <tr>
                <td className="w-40 border-b border-hairline bg-surface-pearl px-4 py-4 align-middle text-center">
                  <div className="text-center">
                    <div className="text-base font-extrabold leading-tight text-[#004e9a] tracking-[-0.3px]">KRC</div>
                    <div className="text-[11px] font-bold text-ink-muted-80 mt-0.5">한국농어촌공사</div>
                  </div>
                </td>
                <td className="border-b border-l border-hairline px-4 py-5 text-center align-middle bg-canvas">
                  <span className="text-[20px] font-extrabold tracking-[-0.5px] text-ink">
                    {title}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>

          {/* Info table and approval blocks */}
          <div className="flex border-b border-hairline divide-x divide-hairline">
            {/* Left: Metadata */}
            <div className="flex-1 bg-canvas">
              <table className="w-full border-collapse text-[12px] h-full">
                <tbody>
                  <tr className="border-b border-hairline">
                    <td className="w-24 bg-surface-pearl border-r border-hairline px-3 py-2.5 font-medium text-ink-muted-80 text-center">현장명</td>
                    <td className="px-3 py-2.5 text-ink font-semibold">{siteName || "-"}</td>
                  </tr>
                  <tr className="border-b border-hairline">
                    <td className="w-24 bg-surface-pearl border-r border-hairline px-3 py-2.5 font-medium text-ink-muted-80 text-center">작성일</td>
                    <td className="px-3 py-2.5 text-ink">{formatDate(writeDate) || "-"}</td>
                  </tr>
                  <tr className="border-b border-hairline">
                    <td className="w-24 bg-surface-pearl border-r border-hairline px-3 py-2.5 font-medium text-ink-muted-80 text-center">작성자</td>
                    <td className="px-3 py-2.5 text-ink">{writer || "-"}</td>
                  </tr>
                  <tr>
                    <td className="w-24 bg-surface-pearl border-r border-hairline px-3 py-2.5 font-medium text-ink-muted-80 text-center">관리기간</td>
                    <td className="px-3 py-2.5 text-ink">{formatPeriod(periodStart, periodEnd) || "-"}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Right: Signature lines */}
            <div className="flex shrink-0 p-3 bg-surface-pearl items-center justify-center gap-6">
              {/* 결재선 */}
              <div className="flex items-center gap-2">
                <div className="text-[11px] font-bold text-ink-muted-48 [writing-mode:vertical-lr] tracking-[2px] mr-1">결재</div>
                <div className="flex gap-2">
                  <StampBox role="공사" name={approverConstruction} />
                  <StampBox role="안전" name={approverSafety} />
                  <StampBox role="현장소장" name={approverSiteManager} />
                </div>
              </div>

              {/* 점검선 */}
              <div className="flex items-center gap-2 border-l border-hairline pl-5">
                <div className="text-[11px] font-bold text-ink-muted-48 [writing-mode:vertical-lr] tracking-[2px] mr-1">점검</div>
                <StampBox role="공사감독" name={inspectorSupervisor} />
              </div>
            </div>
          </div>

          {/* Table contents */}
          <table className="w-full border-collapse text-[12px]">
            <thead className="bg-surface-pearl text-ink-muted-80 border-b border-hairline">
              <tr className="align-middle">
                <Th rowSpan={2} className="w-[15%]">
                  세부작업
                  <br />
                  <span className="text-ink-muted-48">(작업위치)</span>
                </Th>
                <Th rowSpan={2} className="w-[9%]">
                  사용장비
                  <br />
                  /설비/인원
                </Th>
                <Th rowSpan={2} className="w-[18%]">
                  위험요인
                </Th>
                <Th rowSpan={2} className="w-[7%]">
                  재해
                  <br />
                  형태
                </Th>
                <Th colSpan={2}>위험성평가</Th>
                <Th rowSpan={2} className="w-[5%]">
                  위험
                  <br />
                  등급
                </Th>
                <Th rowSpan={2} className="w-[19%]">
                  예방대책
                </Th>
                <Th rowSpan={2} className="w-[9%]">
                  개선후
                  <br />
                  위험성
                  <br />
                  <span className="text-ink-muted-48">(예정일)</span>
                </Th>
                <Th rowSpan={2} className="w-[8%] border-r-0">
                  이행담당
                  <br />
                  <span className="text-ink-muted-48">(확인담당)</span>
                </Th>
              </tr>
              <tr className="border-b border-hairline">
                <Th className="w-[5%]">
                  빈도
                  <br />
                  (3)
                </Th>
                <Th className="w-[5%]">
                  강도
                  <br />
                  (3)
                </Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <Fragment key={i}>
                  <tr className="align-top hover:bg-surface-pearl/40">
                    <Td className="relative text-center font-medium text-ink bg-canvas group">
                      <button
                        type="button"
                        onClick={() => onRemoveRow(i)}
                        className="absolute left-1 top-1.5 text-[11px] text-red-500 opacity-0 group-hover:opacity-100 transition-opacity font-bold"
                        title="이 행 삭제"
                      >
                        🗑️
                      </button>
                      <input
                        className="w-full bg-transparent border-none text-[12px] text-ink font-medium text-center outline-none focus:bg-white focus:ring-1 focus:ring-primary/40 p-1 rounded"
                        value={r.detail_work}
                        placeholder="세부작업 입력"
                        onChange={(e) => onUpdateRow(i, "detail_work", e.target.value)}
                      />
                    </Td>
                    <Td rowSpan={2} className="align-middle text-center bg-canvas">
                      <input
                        className="w-full bg-transparent border-none text-[12px] text-ink text-center outline-none focus:bg-white focus:ring-1 focus:ring-primary/40 p-1 rounded"
                        value={r.equipment}
                        placeholder="사용장비"
                        onChange={(e) => onUpdateRow(i, "equipment", e.target.value)}
                      />
                    </Td>
                    <Td rowSpan={2} className="whitespace-pre-wrap leading-relaxed bg-canvas">
                      <div className="text-[12px] text-ink p-1 leading-relaxed">
                        {r.hazard || <span className="text-ink-muted-48">자동 생성 중...</span>}
                      </div>
                    </Td>
                    <Td rowSpan={2} className="text-center align-middle bg-canvas">
                      <div className="text-[12px] text-ink text-center p-1 font-medium">
                        {r.accident_type || <span className="text-ink-muted-48">-</span>}
                      </div>
                    </Td>
                    <Td rowSpan={2} className="text-center align-middle font-semibold text-ink bg-canvas">
                      <select
                        className="bg-transparent border-none text-[12px] text-ink font-semibold text-center outline-none focus:bg-white focus:ring-1 focus:ring-primary/40 p-1 rounded"
                        value={r.frequency != null ? String(r.frequency) : ""}
                        onChange={(e) => onUpdateRow(i, "frequency", e.target.value ? Number(e.target.value) : null)}
                      >
                        <option value="">-</option>
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                      </select>
                    </Td>
                    <Td rowSpan={2} className="text-center align-middle font-semibold text-ink bg-canvas">
                      <select
                        className="bg-transparent border-none text-[12px] text-ink font-semibold text-center outline-none focus:bg-white focus:ring-1 focus:ring-primary/40 p-1 rounded"
                        value={r.severity != null ? String(r.severity) : ""}
                        onChange={(e) => onUpdateRow(i, "severity", e.target.value ? Number(e.target.value) : null)}
                      >
                        <option value="">-</option>
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                      </select>
                    </Td>
                    <Td rowSpan={2} className="text-center align-middle font-bold text-ink bg-canvas">
                      <span className={`font-bold ${r.risk_grade === "상" ? "text-red-500" : r.risk_grade === "중" ? "text-amber-500" : r.risk_grade === "하" ? "text-green-600" : "text-ink"}`}>
                        {r.risk_grade || "-"}
                      </span>
                    </Td>
                    <Td rowSpan={2} className="whitespace-pre-wrap leading-relaxed bg-canvas">
                      <div className="text-[12px] text-ink p-1 leading-relaxed whitespace-pre-wrap">
                        {r.controls || <span className="text-ink-muted-48">자동 생성 중...</span>}
                      </div>
                    </Td>
                    <Td className="text-center font-medium text-ink bg-canvas">
                      <input
                        className="w-full bg-transparent border-none text-[12px] text-ink text-center font-medium outline-none focus:bg-white focus:ring-1 focus:ring-primary/40 p-1 rounded"
                        value={r.improved_risk}
                        placeholder="1/1 등"
                        onChange={(e) => onUpdateRow(i, "improved_risk", e.target.value)}
                      />
                    </Td>
                    <Td className="text-center font-medium text-ink bg-canvas border-r-0">
                      <input
                        className="w-full bg-transparent border-none text-[12px] text-ink text-center font-medium outline-none focus:bg-white focus:ring-1 focus:ring-primary/40 p-1 rounded"
                        value={r.executor}
                        placeholder="이행담당"
                        onChange={(e) => onUpdateRow(i, "executor", e.target.value)}
                      />
                    </Td>
                  </tr>
                  <tr className="align-top hover:bg-surface-pearl/40 border-b border-hairline last:border-b-0">
                    <Td className="text-center text-ink-muted-48 bg-canvas">
                      <input
                        className="w-full bg-transparent border-none text-[12px] text-ink-muted-48 text-center outline-none focus:bg-white focus:ring-1 focus:ring-primary/40 p-1 rounded"
                        value={r.work_location}
                        placeholder="작업위치"
                        onChange={(e) => onUpdateRow(i, "work_location", e.target.value)}
                      />
                    </Td>
                    <Td className="text-center text-ink-muted-48 bg-canvas">
                      <input
                        className="w-full bg-transparent border-none text-[12px] text-ink-muted-48 text-center outline-none focus:bg-white focus:ring-1 focus:ring-primary/40 p-1 rounded"
                        value={r.improvement_due}
                        placeholder="예정일"
                        onChange={(e) => onUpdateRow(i, "improvement_due", e.target.value)}
                      />
                    </Td>
                    <Td className="text-center text-ink-muted-48 bg-canvas border-r-0">
                      <input
                        className="w-full bg-transparent border-none text-[12px] text-ink-muted-48 text-center outline-none focus:bg-white focus:ring-1 focus:ring-primary/40 p-1 rounded"
                        value={r.verifier}
                        placeholder="확인담당"
                        onChange={(e) => onUpdateRow(i, "verifier", e.target.value)}
                      />
                    </Td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3줄 추가 / 1줄 추가 버튼 추가 */}
      <div className="flex items-center justify-center gap-3 py-2">
        <button
          type="button"
          onClick={() => onAddRows(3)}
          className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 hover:bg-primary/20 px-5 py-2 text-[13px] font-semibold text-primary shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors active:scale-95"
        >
          ➕ 3줄 추가
        </button>
        <button
          type="button"
          onClick={() => onAddRows(1)}
          className="inline-flex items-center gap-1.5 rounded-full border border-hairline hover:bg-surface-pearl px-5 py-2 text-[13px] font-semibold text-ink shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors active:scale-95"
        >
          ➕ 1줄 추가
        </button>
      </div>
    </section>
  );
}

const dash = "-";

function Th({
  children,
  rowSpan,
  colSpan,
  className,
}: {
  children: React.ReactNode;
  rowSpan?: number;
  colSpan?: number;
  className?: string;
}) {
  return (
    <th
      rowSpan={rowSpan}
      colSpan={colSpan}
      className={`border-b border-l border-hairline px-2 py-2 text-center font-medium text-ink-muted-80 first:border-l-0 ${className ?? ""}`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  rowSpan,
  className,
}: {
  children: React.ReactNode;
  rowSpan?: number;
  className?: string;
}) {
  return (
    <td
      rowSpan={rowSpan}
      className={`border-b border-l border-hairline px-2 py-2 first:border-l-0 ${className ?? ""}`}
    >
      {children}
    </td>
  );
}

function Text({
  value,
  onChange,
  type = "text",
  placeholder,
  muted,
}: {
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  muted?: boolean;
}) {
  return (
    <input
      type={type}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      onFocus={() => {
        if (muted && type !== "date") onChange("");
      }}
      className={`w-full rounded-[11px] border border-hairline bg-canvas px-3 py-2 text-[15px] outline-none focus:border-primary-focus focus:ring-2 focus:ring-primary-focus/25 ${
        muted ? "text-ink-muted-48" : "text-ink"
      }`}
    />
  );
}

function PresetChip({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="shrink-0 rounded-full border border-hairline bg-canvas px-3 py-1.5 text-[12px] text-ink-muted-80 transition-colors hover:bg-surface-pearl disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-canvas"
    >
      {label}
    </button>
  );
}

function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-[11px] bg-[#e8e8ed] p-1">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={`min-w-[44px] rounded-[8px] px-3 py-1.5 text-[13px] transition-colors ${
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
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${variantClass} ${disabledClass}`}
    >
      {loading && (
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
      )}
      <span className={loading ? "opacity-60" : ""}>{children}</span>
    </button>
  );
}
