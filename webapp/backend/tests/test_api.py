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
