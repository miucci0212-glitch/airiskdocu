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
) -> str:
    rag_text = "\n".join(
        f"[{i+1}] 공종:{r['trade']} | 세부작업:{r['work_detail']} | "
        f"위험요인:{r['hazard']} | 대책:{r['control']}"
        for i, r in enumerate(rag_results)
    )
    return f"""당신은 건설 현장 위험성평가서를 작성하는 전문가입니다.

## 사용자 입력
- 작업내용: {work_description}
- 장비/기계: {', '.join(equipment) if equipment else '없음'}
- 작업장소: {', '.join(locations) if locations else '없음'}

## 참고 위험성평가 DB (RAG 검색 결과)
{rag_text}

## 지시사항
1. 위 RAG 검색 결과를 기반으로 해당 작업의 위험요인과 안전보건추진계획을 작성하세요.
2. 입력된 장비(예: 그라인더, 용접기)에 맞는 위험요인을 우선 포함하세요.
3. 공통사항(중량물, 화재, 비산먼지 등)도 적절히 포함하세요.
4. 각 항목은 실제로 발생 가능한 구체적 위험 상황을 서술하세요.
5. 안전보건추진계획은 "- " 형식으로 2~4개 항목을 작성하세요.
6. 작업장소와 작업내용은 입력값을 사용하세요.

## 출력 형식
반드시 JSON 배열로만 응답하세요. 각 항목:
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


def _build_krc_prompt(
    items: list[dict],
    rag_hits_per_item: list[list[dict]],
    default_executor: str,
    default_verifier: str,
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
            f"### 입력 항목 {i+1}\n"
            f"- 세부작업: {item.get('detail_work','')}\n"
            f"- 작업위치: {item.get('work_location','')}\n"
            f"- 사용장비/설비/인원: {item.get('equipment','')}\n\n"
            f"RAG 참고:\n{rag_text}\n"
        )

    body = "\n".join(sections)
    return f"""당신은 농어촌공사 건설 현장 위험성평가서를 작성하는 전문가입니다.
아래 입력 항목 {len(items)}개 각각에 대해, 해당 세부작업에서 발생할 수 있는 서로 다른 3가지 주요 위험 상황(위험요인)을 도출하여 총 {3 * len(items)}개의 위험성평가 행을 생성하세요. (입력 항목 1개당 반드시 3개의 독립적인 위험성평가 행이 생성되어야 합니다.)

{body}

## 출력 스펙
- 입력 항목 수의 정확히 3배인 총 {3 * len(items)}개 객체로 구성된 JSON 배열을 반환
- 배열의 순서는 입력 항목 1에 대한 3개 행, 이어서 입력 항목 2에 대한 3개 행 순이어야 합니다.
- 각 객체 필드:
  - hazard (string): 해당 작업 및 장비에서 발생 가능한 구체적인 위험요인 한 문장 (RAG 참고하여 서로 다르게 3개 도출)
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
) -> tuple[list[dict], bool]:
    """LLM으로 KRC 행 데이터를 생성. fallback_used=True면 RAG top-3로 폴백."""
    fallback = []
    for item, hits in zip(items, rag_hits_per_item):
        for j in range(3):
            h = hits[j] if len(hits) > j else (hits[0] if hits else {})
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

    if not api_key:
        return fallback, True

    prompt = _build_krc_prompt(items, rag_hits_per_item, default_executor, default_verifier)
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
        if len(parsed) == 3 * len(items):
            return parsed, False
        logger.warning("krc_llm_attempt1: parsed_len=%d expected=%d preview=%r", len(parsed), 3 * len(items), response.text[:200])
    except Exception as e:
        logger.warning("krc_llm_attempt1_exc: %s: %s", type(e).__name__, e)

    try:
        fix_prompt = prompt + "\n\n반드시 길이 " + str(3 * len(items)) + "인 유효한 JSON 배열만 반환하세요."
        response = model.generate_content(fix_prompt)
        parsed = _parse_krc_response(response.text)
        if len(parsed) == 3 * len(items):
            return parsed, False
        logger.warning("krc_llm_attempt2: parsed_len=%d expected=%d preview=%r", len(parsed), 3 * len(items), response.text[:200])
    except Exception as e:
        logger.warning("krc_llm_attempt2_exc: %s: %s", type(e).__name__, e)

    logger.warning("krc_llm_fallback: returning RAG-only fallback for %d items", len(items))
    return fallback, True


def _build_krc_expand_prompt(
    items: list[dict],
    existing_hazards: list[str],
    count: int,
) -> str:
    items_text = "\n".join(
        f"- 세부작업: {it.get('detail_work','')} / 작업위치: {it.get('work_location','')} / "
        f"사용장비: {it.get('equipment','')}"
        for it in items
    ) or "  (없음)"
    existing_text = "\n".join(f"- {h}" for h in existing_hazards if h) or "  (없음)"

    return f"""당신은 농어촌공사 건설 현장 위험성평가서를 작성하는 전문가입니다.
아래 작업 환경에 대해, 이미 식별된 위험요인과 중복되지 않는 새로운 위험요인 {count}개를 추가로 도출하세요.

## 작업 환경 (전체 항목)
{items_text}

## 이미 식별된 위험요인 (중복 금지)
{existing_text}

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
) -> tuple[list[dict], bool]:
    """기존 위험요인과 중복되지 않는 새 행 count개를 LLM으로 생성. fallback_used=True면 빈 행."""
    empty_fallback = [
        {
            "hazard": "",
            "accident_type": "",
            "frequency": None,
            "severity": None,
            "controls": "",
            "improved_frequency": None,
            "improved_severity": None,
            "improvement_due": "",
            "executor": "",
            "verifier": "",
        }
        for _ in range(count)
    ]
    if count <= 0 or not api_key:
        return empty_fallback, True

    prompt = _build_krc_expand_prompt(items, existing_hazards, count)
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
            return parsed[:count] + empty_fallback[len(parsed):count], False
    except Exception:
        pass

    try:
        fix_prompt = prompt + f"\n\n반드시 길이 {count}인 유효한 JSON 배열만 반환하세요."
        response = model.generate_content(fix_prompt)
        parsed = _parse_krc_response(response.text)
        if len(parsed) >= 1:
            return parsed[:count] + empty_fallback[len(parsed):count], False
    except Exception:
        pass

    return empty_fallback, True


def generate(
    work_description: str,
    equipment: list[str],
    locations: list[str],
    rag_results: list[dict],
    api_key: str,
    thinking_level: str = "balanced",
    timeout: int = 60,
    model_override: Optional[str] = None,
) -> tuple[list[AssessRow], bool]:
    """
    Returns (rows, fallback_used).
    fallback_used=True 이면 LLM 실패로 RAG 원문을 사용.
    """
    prompt = build_prompt(work_description, equipment, locations, rag_results)
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
            return rows, False
    except Exception:
        pass

    try:
        fix_prompt = prompt + "\n\n반드시 유효한 JSON 배열만 반환하세요. 다른 텍스트 없이."
        response = model.generate_content(fix_prompt)
        rows = parse_llm_response(response.text)
        if rows:
            return rows, False
    except Exception:
        pass

    fallback_rows = [
        AssessRow(
            location=locations[0] if locations else "",
            work=work_description,
            hazard=r.get("hazard", ""),
            control=r.get("control", ""),
        )
        for r in rag_results[:12]
    ]
    return fallback_rows, True
