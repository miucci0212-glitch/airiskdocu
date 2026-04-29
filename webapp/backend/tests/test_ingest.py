import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import chromadb
from unittest.mock import patch, MagicMock


def test_build_document_text():
    from rag.ingest import build_document_text
    text = build_document_text(
        trade="(19)창호 및 유리 작업",
        work_detail="출입구 도어 시공",
        hazard="그라인더 보호덮개 미설치로 날 파단 비래",
        control="날접촉방지 보호덮개 설치"
    )
    assert "[공종]" in text
    assert "창호" in text
    assert "[위험요인]" in text
    assert "비래" in text


def test_ingest_creates_collection(tmp_path):
    from rag.ingest import ingest

    import pandas as pd
    xlsx_path = str(tmp_path / "mini.xlsx")
    df = pd.DataFrame({
        "공종": ["(19)창호 및 유리 작업", "(19)창호 및 유리 작업"],
        "세부작업": ["출입구 도어 시공", "몰딩 시공"],
        "위험요인": ["그라인더 날 파단 비래", "케이블 절연 파괴 감전"],
        "재해형태": ["비래", "감전"],
        "안전대책": ["보호덮개 설치", "절연테이프 테이핑"],
    })
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="(19)창호 및 유리 작업", index=False)

    chroma_dir = str(tmp_path / "chroma")
    ingest(xlsx_path=xlsx_path, chroma_dir=chroma_dir, use_local_embedding=True)

    client = chromadb.PersistentClient(path=chroma_dir)
    col = client.get_collection("risk_db")
    assert col.count() == 2


def test_ingest_document_has_metadata(tmp_path):
    from rag.ingest import ingest
    import pandas as pd

    xlsx_path = str(tmp_path / "mini.xlsx")
    df = pd.DataFrame({
        "공종": ["(01)가설전기"],
        "세부작업": ["임시전선 배선"],
        "위험요인": ["전선 피복 손상 감전"],
        "재해형태": ["감전"],
        "안전대책": ["절연테이프 보강"],
    })
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="(01)가설전기", index=False)

    chroma_dir = str(tmp_path / "chroma2")
    ingest(xlsx_path=xlsx_path, chroma_dir=chroma_dir, use_local_embedding=True)

    client = chromadb.PersistentClient(path=chroma_dir)
    col = client.get_collection("risk_db")
    result = col.get(include=["metadatas"])
    meta = result["metadatas"][0]
    assert meta["trade"] == "(01)가설전기"
    assert meta["hazard"] == "전선 피복 손상 감전"
