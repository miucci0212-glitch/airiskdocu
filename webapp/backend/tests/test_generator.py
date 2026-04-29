import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import json
from unittest.mock import MagicMock, patch
from models import AssessRow


SAMPLE_RAG = [
    {
        "trade": "(19)창호 및 유리 작업",
        "work_detail": "출입구 도어 시공",
        "hazard": "그라인더 보호덮개 미설치 날 파단 비래",
        "control": "날접촉방지 보호덮개 설치",
        "sheet": "(19)창호 및 유리 작업",
        "row_id": "(19)창호 및 유리 작업|row0",
    }
]


def test_build_prompt_contains_rag_results():
    from llm.generator import build_prompt
    prompt = build_prompt(
        work_description="출입구 도어 시공",
        equipment=["핸드그라인더"],
        locations=["현장출입구"],
        rag_results=SAMPLE_RAG,
    )
    assert "그라인더" in prompt
    assert "출입구 도어 시공" in prompt
    assert "JSON" in prompt.upper() or "json" in prompt


def test_parse_llm_response_valid():
    from llm.generator import parse_llm_response
    raw = json.dumps([
        {"location": "현장출입구", "work": "도어 시공", "hazard": "비래", "control": "보호덮개 설치", "note": ""}
    ])
    rows = parse_llm_response(raw)
    assert len(rows) == 1
    assert isinstance(rows[0], AssessRow)
    assert rows[0].location == "현장출입구"


def test_parse_llm_response_with_markdown_fence():
    from llm.generator import parse_llm_response
    raw = '```json\n[{"location":"A","work":"B","hazard":"C","control":"D","note":""}]\n```'
    rows = parse_llm_response(raw)
    assert len(rows) == 1


def test_parse_llm_response_invalid_returns_empty():
    from llm.generator import parse_llm_response
    rows = parse_llm_response("not json at all")
    assert rows == []


def test_thinking_budget_mapping():
    from llm.generator import get_thinking_budget
    assert get_thinking_budget("fast") == 0
    assert get_thinking_budget("balanced") == -1
    assert get_thinking_budget("thorough") == 8192
    assert get_thinking_budget("max") == 24576


@patch("llm.generator.genai")
def test_generate_calls_gemini(mock_genai):
    from llm.generator import generate

    fake_response = MagicMock()
    fake_response.text = json.dumps([
        {"location": "현장출입구", "work": "도어 시공",
         "hazard": "비래 위험", "control": "보호덮개 설치", "note": ""}
    ])
    mock_model = MagicMock()
    mock_model.generate_content.return_value = fake_response
    mock_genai.GenerativeModel.return_value = mock_model

    rows, fallback = generate(
        work_description="도어 시공",
        equipment=["그라인더"],
        locations=["현장출입구"],
        rag_results=SAMPLE_RAG,
        api_key="fake-key",
        thinking_level="balanced",
    )
    assert len(rows) == 1
    assert fallback is False
