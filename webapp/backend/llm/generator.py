"""Gemini API 호출 + JSON 파싱으로 위험성평가 행을 생성한다."""
import json
import logging
import re
from typing import Literal, Optional

import google.generativeai as genai

from models import AssessRow

logger = logging.getLogger(__name__)

THINKING_BUDGET_MAP = {
    "fast": 0,
    "balanced": -1,
    "thorough": 8192,
    "max": 24576,
}

MODEL_MAP = {
    "fast": "gemini-2.5-flash",
    "balanced": "gemini-2.5-pro",
    "thorough": "gemini-3.1-pro-preview",
    "max": "gemini-3.1-pro-preview",
}

RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "location": {"type": "string"},
            "work": {"type": "string"},
            "hazard": {"type": "string"},
            "control": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["location", "work", "hazard", "control", "note"],
    },
}


def get_thinking_budget(level: str) -> int:
    return THINKING_BUDGET_MAP.get(level, -1)


def build_prompt(
    work_description: str,
    equipment: list[str],
    locations: list[str],
    rag_results: list[dict],
    generation_mode: str = "hybrid",
    row_count: int = 3,
) -> str:
    rag_text = "\n".join(
        f"[{i+1}] 공종:{r['trade']} | 세부작업:{r['work_detail']} | "
        f"위험요인:{r['hazard']} | 대책:{r['control']}"
        for i, r in enumerate(rag_results)
    )

    if generation_mode == "hybrid":
        guidance = (
            "## 도출 방침 (DB+LLM 혼합)\n"
            "1. RAG 검색 결과는 태영건설 위험성평가 DB의 시드(seed)입니다. 그대로 베끼지 말고 작업·장비·환경에 맞게 재구성하세요.\n"
            "2. RAG에 없는 위험요인이라도 해당 작업에서 실제 발생 가능하다면 일반 건설 안전 지식을 활용해 적극 포함하세요.\n"
            "3. 가능한 한 서로 다른 재해형태(추락·감전·끼임·화재·맞음·깔림·붕괴·베임·근골격계·질병·유해물질 노출 등)를 다양화하세요.\n"
            "4. 입력된 장비(예: 그라인더, 용접기)에 맞는 위험요인을 우선 포함하세요.\n"
            "5. 각 항목은 실제로 발생 가능한 구체적 위험 상황을 서술하세요.\n"
            "6. 안전보건추진계획은 \"- \" 형식으로 2~4개 항목을 작성하세요.\n"
            "7. 작업장소와 작업내용은 입력값을 사용하세요.\n"
        )
    else:  # db
        guidance = (
            "## 도출 방침 (DB 중심)\n"
            "1. RAG 검색 결과에 제시된 태영건설 DB 위험요인을 그대로 활용하거나 가깝게 재서술하세요.\n"
            "2. RAG에서 다루지 않은 주제는 가급적 추가하지 말고, DB 어휘·표현 방식을 유지하세요.\n"
            "3. 입력된 장비(예: 그라인더, 용접기)에 맞는 위험요인을 우선 포함하세요.\n"
            "4. 각 항목은 실제로 발생 가능한 구체적 위험 상황을 서술하세요.\n"
            "5. 안전보건추진계획은 \"- \" 형식으로 2~4개 항목을 작성하세요.\n"
            "6. 작업장소와 작업내용은 입력값을 사용하세요.\n"
        )

    return f"""당신은 건설 현장 위험성평가서를 작성하는 전문가입니다.

## 사용자 입력
- 작업내용: {work_description}
- 장비/기계: {', '.join(equipment) if equipment else '없음'}
- 작업장소: {', '.join(locations) if locations else '없음'}

## 참고 위험성평가 DB (RAG 검색 결과)
{rag_text}

{guidance}
## 출력 형식
반드시 정확히 {row_count}개 객체로 구성된 JSON 배열로만 응답하세요. 각 항목:
{{"location": "작업장소", "work": "작업내용", "hazard": "위험요인 상세 서술", "control": "- 대책1\\n- 대책2", "note": ""}}
"""


def parse_llm_response(raw: str) -> list[AssessRow]:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        data = json.loads(cleaned)
        if not isinstance(data, list):
            return []
        return [
            AssessRow(
                location=str(item.get("location", "")),
                work=str(item.get("work", "")),
                hazard=str(item.get("hazard", "")),
                control=str(item.get("control", "")),
                note=str(item.get("note", "")),
            )
            for item in data
            if isinstance(item, dict)
        ]
    except (json.JSONDecodeError, Exception):
        return []


def compute_grade(freq: Optional[int], sev: Optional[int]) -> str:
    if freq is None or sev is None:
        return ""
    score = freq * sev
    if score >= 6:
        return "상"
    if score >= 3:
        return "중"
    return "하"


# 재해형태별 (빈도, 강도) 휴리스틱 — LLM 폴백에서 등급이 모두 비지 않게 하기 위함
_HIGH_RISK = ("떨어짐", "추락", "감전", "화재", "폭발", "붕괴", "무너짐", "깔림", "익사", "질식", "압사")
_MED_RISK = ("끼임", "협착", "부딪힘", "충돌", "맞음", "낙하", "화상", "유해물질", "질병")
_LOW_RISK = ("베임", "절단", "찰과", "미끄러짐", "넘어짐", "전도", "무리한동작", "근골격계")


def heuristic_freq_sev(accident_type: str, hazard: str = "") -> tuple[int, int]:
    """LLM 누락 시 재해형태/위험요인 텍스트로 (빈도, 강도)를 추정한다."""
    text = f"{accident_type} {hazard}"
    if any(k in text for k in _HIGH_RISK):
        return 2, 3  # 상 (score 6)
    if any(k in text for k in _LOW_RISK):
        return 1, 2  # 하 (score 2)
    if any(k in text for k in _MED_RISK):
        return 2, 2  # 중 (score 4)
    return 2, 2  # 알 수 없으면 중


def heuristic_improved(freq: int, sev: int) -> tuple[int, int]:
    """대책 적용 후 빈도/강도 — 보통 한 단계씩 낮춘다."""
    return max(1, freq - 1), max(1, sev - 1)


# RAG가 3개 unique를 못 줄 때 채우는 일반 위험요인 패턴.
# 건설현장 어디서나 적용 가능한 generic 항목.
_GENERIC_HAZARDS: list[tuple[str, str, str]] = [
    (
        "작업장 정리정돈 미흡으로 통로에 자재·공구가 방치되어 작업자가 걸려 넘어짐",
        "넘어짐",
        "작업 전·후 정리정돈 실시\n작업통로 확보 및 자재 적치구역 분리\n정리정돈 일일 점검",
    ),
    (
        "개인보호구(안전모·안전화·장갑) 미착용 상태로 작업 중 부주의로 인한 신체 부상",
        "맞음",
        "안전모·안전화·보호장갑 등 개인보호구 착용 철저\n작업 전 보호구 착용 상태 확인\n미착용 시 작업 중지 조치",
    ),
    (
        "작업장 주변 분진·유해물질 노출로 인한 호흡기·피부 자극",
        "질병",
        "방진마스크·보안경·보호장갑 착용\n작업장 환기 및 분진 발생 최소화\nMSDS 비치 및 숙지",
    ),
    (
        "협소한 작업 공간에서 무리한 자세로 장시간 작업 중 근골격계 손상",
        "무리한동작",
        "충분한 작업공간 확보\n작업 중 정기적 휴식 시간 부여\n보조기구·작업대 활용",
    ),
    (
        "작업 종료 후 잔재물·공구 미처리로 인한 2차 재해 발생",
        "맞음",
        "작업 종료 후 잔재물 즉시 정리·처리\n위험구역 통제 및 안내표지 설치\n다음 공정 작업자 안전 확보",
    ),
    (
        "비상시 대피로·소화기 등 안전시설 미숙지로 초기 대응 지연",
        "화재",
        "작업 전 대피로 및 소화기 위치 숙지\n비상연락망 게시\n월 1회 비상대응 훈련 실시",
    ),
]


def generic_filler(index: int) -> dict:
    """RAG 결과가 부족할 때 사용할 generic 위험요인 1개."""
    hz, accident, controls = _GENERIC_HAZARDS[index % len(_GENERIC_HAZARDS)]
    freq, sev = heuristic_freq_sev(accident, hz)
    imp_freq, imp_sev = heuristic_improved(freq, sev)
    return {
        "hazard": hz,
        "accident_type": accident,
        "frequency": freq,
        "severity": sev,
        "controls": controls,
        "improved_frequency": imp_freq,
        "improved_severity": imp_sev,
        "improvement_due": "",
        "executor": "",
        "verifier": "",
    }


def _build_krc_prompt(
    items: list[dict],
    rag_hits_per_item: list[list[dict]],
    default_executor: str,
    default_verifier: str,
    row_counts: list[int],
    generation_mode: str = "hybrid",
) -> str:
    sections = []
    for i, (item, hits) in enumerate(zip(items, rag_hits_per_item)):
        rag_text = "\n".join(
            f"  [{j+1}] {h.get('work','')} > {h.get('unit_work','')} / {h.get('sub_work','')}\n"
            f"      위험요인: {h.get('hazard','')}\n"
            f"      재해형태: {h.get('accident','')}\n"
            f"      대책: {str(h.get('controls',''))[:300]}"
            for j, h in enumerate(hits[:5])
        ) or "  (RAG 결과 없음)"
        sections.append(
            f"### 입력 항목 {i+1} (생성 행 수: {row_counts[i]})\n"
            f"- 세부작업: {item.get('detail_work','')}\n"
            f"- 작업위치: {item.get('work_location','')}\n"
            f"- 사용장비/설비/인원: {item.get('equipment','')}\n\n"
            f"RAG 참고:\n{rag_text}\n"
        )

    body = "\n".join(sections)
    total_rows = sum(row_counts)
    counts_summary = ", ".join(
        f"항목 {i+1}: {row_counts[i]}행" for i in range(len(items))
    )

    if generation_mode == "hybrid":
        guidance = (
            "## 도출 방침 (DB+LLM 혼합)\n"
            "- RAG 참고는 농어촌공사 DB에서 가져온 시드(seed)입니다. 그대로 베끼지 말고 작업·장비·환경에 맞게 재구성하세요.\n"
            "- RAG에 없는 위험요인이라도 해당 작업에서 실제 발생 가능하다면 일반 건설 안전 지식을 활용해 적극 포함하세요.\n"
            "- 입력 항목별 지정 행 수만큼 가능한 한 서로 다른 재해형태를 다루도록 다양화하세요 "
            "(예: 추락·감전·끼임·화재·맞음·깔림·붕괴·베임·근골격계·질병·유해물질 노출 등).\n"
            "- 표현·어조는 농어촌공사 위험성평가서 양식에 맞춰 간결한 한 문장으로 작성하세요.\n"
        )
        hazard_field_desc = (
            "hazard (string): 해당 작업·장비·환경에서 발생 가능한 구체적 위험요인 한 문장. "
            "RAG를 시드로 활용하되 일반 건설 안전 지식을 결합해 폭넓게 도출."
        )
    else:  # db
        guidance = (
            "## 도출 방침 (DB 중심)\n"
            "- RAG 참고에 제시된 농어촌공사 DB 위험요인을 그대로 활용하거나 가깝게 재서술하세요.\n"
            "- RAG에서 다루지 않은 주제는 가급적 추가하지 말고, DB 어휘와 표현 방식을 유지하세요.\n"
            "- 입력 항목별 지정 행 수만큼 서로 중복되지 않게 RAG 결과에서 골라 구성하세요.\n"
        )
        hazard_field_desc = (
            "hazard (string): RAG에 등장한 농어촌공사 DB 위험요인을 기반으로 작성한 한 문장. "
            "DB 어휘를 유지하고 임의 확장 금지."
        )

    return f"""당신은 농어촌공사 건설 현장 위험성평가서를 작성하는 전문가입니다.
아래 입력 항목 {len(items)}개 각각에 대해, 해당 세부작업에서 발생할 수 있는 서로 다른 주요 위험 상황(위험요인)을 도출하여 총 {total_rows}개의 위험성평가 행을 생성하세요.
항목별 생성해야 할 행 수는 다음과 같습니다: {counts_summary}.
각 항목은 지정된 행 수만큼 서로 다른 독립적인 위험성평가 행을 반드시 생성해야 합니다.

{body}

{guidance}
## 출력 스펙
- 총 {total_rows}개 객체로 구성된 JSON 배열을 반환
- 배열의 순서는 입력 항목 1에 대한 {row_counts[0] if row_counts else 0}개 행, 이어서 입력 항목 2에 대한 행... 순서로 이어집니다 ({counts_summary}).
- 각 객체 필드:
  - {hazard_field_desc}
  - accident_type (string): 재해형태 단답 (예: 떨어짐, 부딪힘, 끼임, 감전, 화재, 맞음, 깔림, 베임, 무리한동작 등)
  - frequency (int 1-3): 빈도 (1=낮음, 2=보통, 3=높음)
  - severity (int 1-3): 강도 (1=경상, 2=중상, 3=중대)
  - controls (string): 해당 위험요인을 예방하기 위한 구체적인 안전대책 2-4개를 줄바꿈("\\n")으로 구분
  - improved_frequency (int 1-3): 대책 적용 후 빈도 (일반적으로 frequency 이하)
  - improved_severity (int 1-3): 대책 적용 후 강도 (일반적으로 severity 이하)
  - improvement_due (string): 개선예정일 ("")
  - executor (string): 이행담당 ("")
  - verifier (string): 확인담당 ("")

반드시 유효한 JSON 배열만 반환하세요. 다른 텍스트 없이.
"""


def _parse_krc_response(raw: str) -> list[dict]:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        data = json.loads(cleaned)
        if not isinstance(data, list):
            return []
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            out.append({
                "hazard": str(item.get("hazard", "")),
                "accident_type": str(item.get("accident_type", "")),
                "frequency": item.get("frequency"),
                "severity": item.get("severity"),
                "controls": str(item.get("controls", "")),
                "improved_frequency": item.get("improved_frequency"),
                "improved_severity": item.get("improved_severity"),
                "improvement_due": str(item.get("improvement_due", "")),
                "executor": str(item.get("executor", "")),
                "verifier": str(item.get("verifier", "")),
            })
        return out
    except (json.JSONDecodeError, Exception):
        return []


def generate_krc(
    items: list[dict],
    rag_hits_per_item: list[list[dict]],
    api_key: str,
    default_executor: str = "작업책임자",
    default_verifier: str = "공사감독",
    thinking_level: str = "balanced",
    model_override: Optional[str] = None,
    generation_mode: Literal["db", "hybrid"] = "hybrid",
    row_counts: Optional[list[int]] = None,
) -> tuple[list[dict], bool]:
    """LLM으로 KRC 행 데이터를 생성. fallback_used=True면 RAG로 폴백.

    row_counts: 항목별 생성 행 수 (None이면 모두 3행).

    generation_mode:
      - "db": RAG hits를 거의 그대로 재서술 (DB 어휘 유지)
      - "hybrid": RAG를 시드로 LLM이 일반 건설지식을 결합해 폭넓게 확장
    """
    if row_counts is None:
        row_counts = [3] * len(items)
    if len(row_counts) != len(items):
        raise ValueError(
            f"row_counts length {len(row_counts)} != items length {len(items)}"
        )

    total_rows = sum(row_counts)

    fallback = []
    generic_counter = 0
    for item, hits, n_rows in zip(items, rag_hits_per_item, row_counts):
        # hazard 텍스트 기준으로 중복 제거 — ChromaDB가 거의 동일한 문서를 여러 번 돌려줘도
        # 같은 항목에 동일 위험요인이 들어가지 않게 한다.
        seen_hazards: set[str] = set()
        unique_hits: list[dict] = []
        for h in hits:
            hz = str(h.get("hazard", "")).strip()
            if hz and hz in seen_hazards:
                continue
            seen_hazards.add(hz)
            unique_hits.append(h)
            if len(unique_hits) >= n_rows:
                break

        for j in range(n_rows):
            if j < len(unique_hits):
                h = unique_hits[j]
                hazard = str(h.get("hazard", ""))
                accident = str(h.get("accident", ""))
                freq, sev = heuristic_freq_sev(accident, hazard)
                imp_freq, imp_sev = heuristic_improved(freq, sev)
                fallback.append({
                    "hazard": hazard,
                    "accident_type": accident,
                    "frequency": freq,
                    "severity": sev,
                    "controls": str(h.get("controls", "")),
                    "improved_frequency": imp_freq,
                    "improved_severity": imp_sev,
                    "improvement_due": "",
                    "executor": "",
                    "verifier": "",
                })
            else:
                # RAG가 unique를 다 못 채우면 generic 위험요인으로 보충
                fallback.append(generic_filler(generic_counter))
                generic_counter += 1

    if not api_key:
        return fallback, True

    prompt = _build_krc_prompt(
        items, rag_hits_per_item, default_executor, default_verifier,
        row_counts=row_counts,
        generation_mode=generation_mode,
    )
    budget = get_thinking_budget(thinking_level)
    model_name = model_override or MODEL_MAP.get(thinking_level, "gemini-2.5-pro")

    generation_config = {"response_mime_type": "application/json"}
    if budget == 0:
        generation_config["thinking_config"] = {"thinking_budget": 0}
    elif budget > 0:
        generation_config["thinking_config"] = {"thinking_budget": budget}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name, generation_config=generation_config)

    try:
        response = model.generate_content(prompt)
        parsed = _parse_krc_response(response.text)
        if len(parsed) == total_rows:
            return parsed, False
        logger.warning("krc_llm_attempt1: parsed_len=%d expected=%d preview=%r", len(parsed), total_rows, response.text[:200])
    except Exception as e:
        logger.warning("krc_llm_attempt1_exc: %s: %s", type(e).__name__, e)

    try:
        fix_prompt = prompt + "\n\n반드시 길이 " + str(total_rows) + "인 유효한 JSON 배열만 반환하세요."
        response = model.generate_content(fix_prompt)
        parsed = _parse_krc_response(response.text)
        if len(parsed) == total_rows:
            return parsed, False
        logger.warning("krc_llm_attempt2: parsed_len=%d expected=%d preview=%r", len(parsed), total_rows, response.text[:200])
    except Exception as e:
        logger.warning("krc_llm_attempt2_exc: %s: %s", type(e).__name__, e)

    logger.warning("krc_llm_fallback: returning RAG-only fallback for %d items", len(items))
    return fallback, True


def _build_krc_expand_prompt(
    items: list[dict],
    existing_hazards: list[str],
    count: int,
    rag_hits: Optional[list[dict]] = None,
    generation_mode: str = "hybrid",
) -> str:
    items_text = "\n".join(
        f"- 세부작업: {it.get('detail_work','')} / 작업위치: {it.get('work_location','')} / "
        f"사용장비: {it.get('equipment','')}"
        for it in items
    ) or "  (없음)"
    existing_text = "\n".join(f"- {h}" for h in existing_hazards if h) or "  (없음)"

    rag_text = ""
    if rag_hits:
        seen: set[str] = set()
        bullets: list[str] = []
        for h in rag_hits:
            hz = str(h.get("hazard", "")).strip()
            if not hz or hz in seen:
                continue
            seen.add(hz)
            bullets.append(
                f"- {hz} / 재해형태: {h.get('accident','')} / 대책: {str(h.get('controls',''))[:200]}"
            )
            if len(bullets) >= 8:
                break
        if bullets:
            rag_text = "\n## 농어촌공사 DB 참고 (RAG)\n" + "\n".join(bullets) + "\n"

    if generation_mode == "hybrid":
        guidance = (
            "## 도출 방침 (DB+LLM 혼합)\n"
            "- RAG 참고가 있다면 시드로 활용하되, RAG에 없는 위험요인이라도 작업 환경에 실제로 존재하면 일반 건설 안전 지식을 활용해 적극 포함하세요.\n"
            "- 이미 식별된 위험요인과 재해형태가 겹치지 않도록 다양화 (추락·감전·끼임·화재·맞음·깔림·붕괴·베임·근골격계·질병·유해물질 노출 등).\n"
        )
    else:  # db
        guidance = (
            "## 도출 방침 (DB 중심)\n"
            "- RAG 참고에 제시된 농어촌공사 DB 위험요인을 우선 활용하세요.\n"
            "- DB 어휘·표현을 유지하고, DB에 없는 주제로의 임의 확장은 피하세요.\n"
        )

    return f"""당신은 농어촌공사 건설 현장 위험성평가서를 작성하는 전문가입니다.
아래 작업 환경에 대해, 이미 식별된 위험요인과 중복되지 않는 새로운 위험요인 {count}개를 추가로 도출하세요.

## 작업 환경 (전체 항목)
{items_text}

## 이미 식별된 위험요인 (중복 금지)
{existing_text}
{rag_text}
{guidance}
## 출력 스펙
- 정확히 {count}개 객체로 구성된 JSON 배열
- 각 객체 필드:
  - hazard (string): 위 작업 환경에서 발생 가능한 새로운 위험요인 한 문장 (이미 식별된 항목과 시나리오가 달라야 함)
  - accident_type (string): 재해형태 단답 (예: 떨어짐, 부딪힘, 끼임, 감전, 화재, 맞음, 깔림, 베임, 무리한동작 등)
  - frequency (int 1-3): 빈도 (1=낮음, 2=보통, 3=높음)
  - severity (int 1-3): 강도 (1=경상, 2=중상, 3=중대)
  - controls (string): 구체적인 안전대책 2-4개를 줄바꿈("\\n")으로 구분
  - improved_frequency (int 1-3): 대책 적용 후 빈도 (일반적으로 frequency 이하)
  - improved_severity (int 1-3): 대책 적용 후 강도 (일반적으로 severity 이하)
  - improvement_due (string): "" 빈 문자열
  - executor (string): "" 빈 문자열
  - verifier (string): "" 빈 문자열

반드시 유효한 JSON 배열만 반환하세요. 다른 텍스트 없이.
"""


def expand_krc(
    items: list[dict],
    existing_hazards: list[str],
    count: int,
    api_key: str,
    model_override: Optional[str] = None,
    rag_hits: Optional[list[dict]] = None,
    generation_mode: Literal["db", "hybrid"] = "hybrid",
) -> tuple[list[dict], bool]:
    """기존 위험요인과 중복되지 않는 새 행 count개를 LLM으로 생성.
    fallback_used=True면 RAG hits에서 기존과 겹치지 않는 항목으로 채우거나(없으면) 빈 행."""

    def build_rag_fallback() -> list[dict]:
        existing_set = {h.strip() for h in existing_hazards if h and h.strip()}
        picked: list[dict] = []
        seen: set[str] = set()
        for h in rag_hits or []:
            hz = str(h.get("hazard", "")).strip()
            if not hz or hz in existing_set or hz in seen:
                continue
            seen.add(hz)
            accident = str(h.get("accident", ""))
            freq, sev = heuristic_freq_sev(accident, hz)
            imp_freq, imp_sev = heuristic_improved(freq, sev)
            picked.append({
                "hazard": hz,
                "accident_type": accident,
                "frequency": freq,
                "severity": sev,
                "controls": str(h.get("controls", "")),
                "improved_frequency": imp_freq,
                "improved_severity": imp_sev,
                "improvement_due": "",
                "executor": "",
                "verifier": "",
            })
            if len(picked) >= count:
                break
        # 부족한 만큼 generic 위험요인으로 보충 (기존/현재 picked의 hazard 텍스트 회피)
        used = existing_set | {p["hazard"] for p in picked}
        gi = 0
        while len(picked) < count and gi < len(_GENERIC_HAZARDS) * 2:
            cand = generic_filler(gi)
            gi += 1
            if cand["hazard"] in used:
                continue
            used.add(cand["hazard"])
            picked.append(cand)
        return picked

    if count <= 0 or not api_key:
        return build_rag_fallback(), True

    prompt = _build_krc_expand_prompt(
        items, existing_hazards, count,
        rag_hits=rag_hits, generation_mode=generation_mode,
    )
    model_name = model_override or "gemini-2.5-flash"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={"response_mime_type": "application/json"},
    )

    try:
        response = model.generate_content(prompt)
        parsed = _parse_krc_response(response.text)
        if len(parsed) >= 1:
            rag_pad = build_rag_fallback()
            return parsed[:count] + rag_pad[len(parsed):count], False
    except Exception as e:
        logger.warning("krc_expand_attempt1_exc: %s: %s", type(e).__name__, e)

    try:
        fix_prompt = prompt + f"\n\n반드시 길이 {count}인 유효한 JSON 배열만 반환하세요."
        response = model.generate_content(fix_prompt)
        parsed = _parse_krc_response(response.text)
        if len(parsed) >= 1:
            rag_pad = build_rag_fallback()
            return parsed[:count] + rag_pad[len(parsed):count], False
    except Exception as e:
        logger.warning("krc_expand_attempt2_exc: %s: %s", type(e).__name__, e)

    logger.warning("krc_expand_fallback: RAG fallback for %d items", count)
    return build_rag_fallback(), True


def generate(
    work_description: str,
    equipment: list[str],
    locations: list[str],
    rag_results: list[dict],
    api_key: str,
    thinking_level: str = "balanced",
    timeout: int = 60,
    model_override: Optional[str] = None,
    generation_mode: Literal["db", "hybrid"] = "hybrid",
    row_count: int = 3,
) -> tuple[list[AssessRow], bool]:
    """
    Returns (rows, fallback_used).
    fallback_used=True 이면 LLM 실패로 RAG 원문을 사용.

    generation_mode:
      - "db": RAG hits를 거의 그대로 재서술 (DB 어휘 유지)
      - "hybrid": RAG를 시드로 LLM이 일반 건설지식을 결합해 폭넓게 확장

    row_count: 생성할 행의 개수 (기본 3, 최대 12).
    """
    row_count = max(1, min(int(row_count), 12))
    prompt = build_prompt(
        work_description, equipment, locations, rag_results,
        generation_mode=generation_mode, row_count=row_count,
    )
    budget = get_thinking_budget(thinking_level)
    model_name = model_override or MODEL_MAP.get(thinking_level, "gemini-2.5-pro")

    generation_config = {
        "response_mime_type": "application/json",
    }
    if budget == 0:
        generation_config["thinking_config"] = {"thinking_budget": 0}
    elif budget > 0:
        generation_config["thinking_config"] = {"thinking_budget": budget}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,
    )

    try:
        response = model.generate_content(prompt)
        rows = parse_llm_response(response.text)
        if rows:
            return rows[:row_count], False
    except Exception:
        pass

    try:
        fix_prompt = prompt + f"\n\n반드시 정확히 {row_count}개 객체로 구성된 유효한 JSON 배열만 반환하세요. 다른 텍스트 없이."
        response = model.generate_content(fix_prompt)
        rows = parse_llm_response(response.text)
        if rows:
            return rows[:row_count], False
    except Exception:
        pass

    fallback_rows = [
        AssessRow(
            location=locations[0] if locations else "",
            work=work_description,
            hazard=r.get("hazard", ""),
            control=r.get("control", ""),
        )
        for r in rag_results[:row_count]
    ]
    return fallback_rows, True
