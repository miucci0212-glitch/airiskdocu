import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pandas as pd
from rag.ingest import ingest


@pytest.fixture(scope="module")
def chroma_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("chroma")
    xlsx = d / "mini.xlsx"
    data = {
        "공종": ["(19)창호 및 유리 작업"] * 3 + ["(07)용접 작업"] * 2,
        "세부작업": ["출입구 도어 시공", "몰딩 시공", "창호 설치", "용접 작업", "그라인더 작업"],
        "위험요인": [
            "그라인더 날 파단 비래",
            "케이블 절연 감전",
            "유리 파손 베임",
            "용접 흄 호흡기",
            "그라인더 보호덮개 미설치",
        ],
        "재해형태": ["비래", "감전", "베임", "직업병", "비래"],
        "안전대책": [
            "보호덮개 설치",
            "절연테이프",
            "안전장갑 착용",
            "방진마스크",
            "보호덮개 설치",
        ],
    }
    df = pd.DataFrame(data)
    with pd.ExcelWriter(str(xlsx), engine="openpyxl") as w:
        df.iloc[:3].to_excel(w, sheet_name="(19)창호 및 유리 작업", index=False)
        df.iloc[3:].to_excel(w, sheet_name="(07)용접 작업", index=False)
    ingest(str(xlsx), str(d / "db"), use_local_embedding=True)
    return str(d / "db")


def test_retrieve_returns_results(chroma_dir):
    from rag.retriever import retrieve
    results = retrieve(
        query="출입구 도어 시공 핸드그라인더",
        chroma_dir=chroma_dir,
        top_k=3,
        use_local_embedding=True,
    )
    assert len(results) > 0


def test_retrieve_result_has_required_keys(chroma_dir):
    from rag.retriever import retrieve
    results = retrieve(
        query="용접 작업",
        chroma_dir=chroma_dir,
        top_k=2,
        use_local_embedding=True,
    )
    for r in results:
        assert "trade" in r
        assert "hazard" in r
        assert "control" in r
        assert "sheet" in r


def test_retrieve_equipment_filter(chroma_dir):
    from rag.retriever import retrieve
    results = retrieve(
        query="그라인더",
        chroma_dir=chroma_dir,
        top_k=5,
        equipment_keywords=["그라인더"],
        use_local_embedding=True,
    )
    grinder_hits = [r for r in results if "그라인더" in r["hazard"] or "그라인더" in r["control"]]
    assert len(grinder_hits) >= 1
