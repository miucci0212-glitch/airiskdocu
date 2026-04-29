"""Gemini API 호출 + JSON 파싱으로 위험성평가 행을 생성한다."""
import json
import re
from typing import Literal

import google.generativeai as genai

from models import AssessRow

THINKING_BUDGET_MAP = {
    "fast": 0,
    "balanced": -1,
    "thorough": 8192,
    "max": 24576,
}

MODEL_MAP = {
    "fast": "gemini-2.5-flash",
    "balanced": "gemini-2.5-pro",
    "thorough": "gemini-2.5-pro",
    "max": "gemini-2.5-pro",
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


def generate(
    work_description: str,
    equipment: list[str],
    locations: list[str],
    rag_results: list[dict],
    api_key: str,
    thinking_level: str = "balanced",
    timeout: int = 60,
) -> tuple[list[AssessRow], bool]:
    """
    Returns (rows, fallback_used).
    fallback_used=True 이면 LLM 실패로 RAG 원문을 사용.
    """
    prompt = build_prompt(work_description, equipment, locations, rag_results)
    budget = get_thinking_budget(thinking_level)
    model_name = MODEL_MAP.get(thinking_level, "gemini-2.5-pro")

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
