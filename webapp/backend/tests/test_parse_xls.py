import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest


XLS_PATH = os.path.join(
    os.path.dirname(__file__), "../../../최초위험성평가 기초자료-건축_REV1.xls"
)
OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "../data/source/risk_db.xlsx"
)


def test_xls_file_exists():
    assert os.path.exists(XLS_PATH), f"XLS 파일 없음: {XLS_PATH}"


def test_parse_produces_xlsx(tmp_path):
    from scripts.parse_xls import parse_xls_to_xlsx
    out = tmp_path / "out.xlsx"
    parse_xls_to_xlsx(XLS_PATH, str(out))
    assert out.exists()


def test_xlsx_has_at_least_38_data_sheets(tmp_path):
    from scripts.parse_xls import parse_xls_to_xlsx
    out = tmp_path / "out.xlsx"
    parse_xls_to_xlsx(XLS_PATH, str(out))
    xl = pd.ExcelFile(str(out))
    data_sheets = [s for s in xl.sheet_names if s not in ("표지", "공종분류표")]
    assert len(data_sheets) >= 38


def test_data_sheet_has_required_columns(tmp_path):
    from scripts.parse_xls import parse_xls_to_xlsx, REQUIRED_COLS
    out = tmp_path / "out.xlsx"
    parse_xls_to_xlsx(XLS_PATH, str(out))
    xl = pd.ExcelFile(str(out))
    data_sheets = [s for s in xl.sheet_names if s not in ("표지", "공종분류표")]
    df = pd.read_excel(str(out), sheet_name=data_sheets[0])
    for col in REQUIRED_COLS:
        assert col in df.columns, f"컬럼 없음: {col}"
