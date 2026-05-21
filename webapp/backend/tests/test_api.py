import json
import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import httpx
from fastapi.testclient import TestClient


FIXTURE = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures/sample_request.json")))


@pytest.fixture(scope="module")
def app_with_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("app")
    xlsx_path = str(d / "mini.xlsx")
    df = pd.DataFrame({
        "공종": ["(19)창호 및 유리 작업"],
        "세부작업": ["출입구 도어 시공"],
        "위험요인": ["그라인더 보호덮개 미설치 날 파단 비래"],
        "재해형태": ["비래"],
        "안전대책": ["날접촉방지 보호덮개 설치"],
    })
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="(19)창호 및 유리 작업", index=False)

    from rag.ingest import ingest
    chroma_dir = str(d / "chroma")
    ingest(xlsx_path, chroma_dir, use_local_embedding=True)

    from excel.template_builder import build_template
    template_path = str(d / "template.xlsx")
    build_template(template_path, cell_map_path="template/cell_map.yaml")

    os.environ["CHROMA_PERSIST_DIR"] = chroma_dir
    os.environ["SOURCE_XLSX_PATH"] = xlsx_path
    os.environ["TEMPLATE_XLSX_PATH"] = template_path
    os.environ["GEMINI_API_KEY"] = "test-fake-key"

    from main import app
    return app


def test_health_check(app_with_db):
    client = TestClient(app_with_db)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@patch("main.generate")
@patch("main.retrieve_for_request")
def test_assess_endpoint(mock_retrieve, mock_generate, app_with_db):
    from models import AssessRow
    mock_retrieve.return_value = [
        {"trade": "창호", "work_detail": "도어", "hazard": "비래", "control": "보호덮개", "sheet": "창호", "row_id": "창호|row0", "distance": 0.1}
    ]
    mock_generate.return_value = (
        [AssessRow(location="현장출입구", work="도어 시공", hazard="비래", control="보호덮개 설치", note="")],
        False,
    )
    client = TestClient(app_with_db)
    resp = client.post("/api/assess", json=FIXTURE)
    assert resp.status_code == 200
    data = resp.json()
    assert "rows" in data
    assert len(data["rows"]) >= 1


@patch("main.generate")
@patch("main.retrieve_for_request")
def test_download_endpoint_returns_xlsx(mock_retrieve, mock_generate, app_with_db):
    from models import AssessRow
    mock_retrieve.return_value = [
        {"trade": "창호", "work_detail": "도어", "hazard": "비래", "control": "보호덮개", "sheet": "창호", "row_id": "창호|row0", "distance": 0.1}
    ]
    mock_generate.return_value = (
        [AssessRow(location="현장출입구", work="도어 시공", hazard="비래", control="보호덮개 설치", note="")],
        False,
    )
    client = TestClient(app_with_db)
    payload = {
        "request": FIXTURE,
        "rows": [{"location": "현장출입구", "work": "도어 시공", "hazard": "비래", "control": "보호덮개 설치", "note": ""}],
    }
    resp = client.post("/api/download", json=payload)
    assert resp.status_code == 200
    assert "spreadsheet" in resp.headers["content-type"]


@patch("main.generate_krc")
@patch("main.retrieve_krc")
def test_krc_assess_endpoint(mock_retrieve_krc, mock_generate_krc, app_with_db):
    mock_retrieve_krc.return_value = [
        {
            "no": 1,
            "project": "KRC",
            "work": "창호",
            "unit_work": "도어",
            "sub_work": "도어 시공",
            "hazard": "비래",
            "accident": "비래",
            "controls": "보호덮개",
            "laws": "법령",
            "permit": "대상",
            "distance": 0.1,
        }
    ]
    mock_generate_krc.return_value = (
        [
            {
                "hazard": "그라인더 날 파단 비래 1",
                "accident_type": "떨어짐",
                "frequency": 2,
                "severity": 2,
                "controls": "대책 1\n대책 2",
                "improved_frequency": 1,
                "improved_severity": 2,
                "improvement_due": "",
                "executor": "",
                "verifier": "",
            },
            {
                "hazard": "그라인더 날 파단 비래 2",
                "accident_type": "끼임",
                "frequency": 1,
                "severity": 2,
                "controls": "대책 1\n대책 2",
                "improved_frequency": 1,
                "improved_severity": 1,
                "improvement_due": "",
                "executor": "",
                "verifier": "",
            },
            {
                "hazard": "그라인더 날 파단 비래 3",
                "accident_type": "부딪힘",
                "frequency": 2,
                "severity": 1,
                "controls": "대책 1\n대책 2",
                "improved_frequency": 1,
                "improved_severity": 1,
                "improvement_due": "",
                "executor": "",
                "verifier": "",
            },
        ],
        False,
    )
    client = TestClient(app_with_db)
    payload = {
        "metadata": {
            "krc_type": "수시",
            "site_name": "서면 어반센트 데시앙 신축공사",
            "write_date": "2026-05-21",
            "writer": "김재한",
            "period_start": "2026-05-21",
            "period_end": "2026-06-19",
            "approver_construction": "김재한",
            "approver_safety": "홍길동",
            "approver_site_manager": "홍길동",
            "inspector_supervisor": "홍길동",
        },
        "items": [
            {
                "detail_work": "출입구 도어 시공 및 고정 작업",
                "work_location": "현장출입구",
                "equipment": "핸드그라인더, 고속절단기, 수공구",
            }
        ],
    }
    resp = client.post("/api/krc/assess", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "rows" in data
    assert len(data["rows"]) == 3
    assert data["rows"][0]["detail_work"] == "출입구 도어 시공 및 고정 작업"
    assert data["rows"][0]["hazard"] == "그라인더 날 파단 비래 1"
    assert data["rows"][0]["executor"] == ""
    assert data["rows"][0]["verifier"] == ""
    assert data["rows"][0]["improvement_due"] == ""


@patch("main.fill_krc_template")
def test_krc_download_endpoint(mock_fill, app_with_db):
    mock_fill.side_effect = lambda metadata, rows, template_dir, output_path: open(output_path, "wb").write(b"dummy excel data")
    client = TestClient(app_with_db)
    payload = {
        "metadata": {
            "krc_type": "수시",
            "site_name": "서면 어반센트 데시앙 신축공사",
            "write_date": "2026-05-21",
            "writer": "김재한",
            "period_start": "2026-05-21",
            "period_end": "2026-06-19",
            "approver_construction": "김재한",
            "approver_safety": "홍길동",
            "approver_site_manager": "홍길동",
            "inspector_supervisor": "홍길동",
        },
        "rows": [
            {
                "detail_work": "작업 1",
                "work_location": "위치 1",
                "equipment": "장비 1",
                "hazard": "위험 1",
                "accident_type": "재해 1",
                "frequency": 2,
                "severity": 2,
                "risk_grade": "중",
                "controls": "대책 1",
                "improved_risk": "1/2 (하)",
                "improvement_due": "",
                "executor": "",
                "verifier": "",
            }
        ],
    }
    resp = client.post("/api/krc/download", json=payload)
    assert resp.status_code == 200
    assert "spreadsheet" in resp.headers["content-type"]


