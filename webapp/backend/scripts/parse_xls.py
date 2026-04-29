"""1회 실행: 원본 .xls를 .xlsx로 변환하고 데이터를 정규화한다."""
import os
import sys
import xlrd
import pandas as pd


REQUIRED_COLS = ["공종", "세부작업", "위험요인", "재해형태", "안전대책"]

SKIP_SHEETS = {"표지", "공종분류표"}

# 원본 컬럼명 → 정규화 컬럼명 매핑 (시트마다 약간씩 다름)
COL_ALIASES = {
    "세부단위\n작     업": "세부작업",
    "세부단위 작업": "세부작업",
    "세부단위작업": "세부작업",
    "안전보건 대책": "안전대책",
    "안전보건대책": "안전대책",
    "위험요인": "위험요인",
    "재해\n형태": "재해형태",
    "재해형태": "재해형태",
    "발   생\n가능성": "발생가능성",
    "발생가능성": "발생가능성",
    "피   해\n심각성": "피해심각성",
    "피해심각성": "피해심각성",
    "위험성\n등   급": "위험성등급",
    "위험성등급": "위험성등급",
    "구분": "구분",
}


def _find_header_rows(sheet):
    """
    메인 헤더 행(위험요인 텍스트 포함)과 서브헤더 행 인덱스를 반환.
    XLS 구조: 행 2 = 메인 헤더, 행 3 = 서브헤더(재해형태, 발생가능성 등).
    """
    for row_idx in range(min(10, sheet.nrows)):
        for col_idx in range(sheet.ncols):
            val = str(sheet.cell_value(row_idx, col_idx)).strip()
            if "위험요인" in val:
                sub_row = row_idx + 1 if row_idx + 1 < sheet.nrows else row_idx
                return row_idx, sub_row
    return 0, 1


def _build_column_names(sheet, header_row: int, sub_header_row: int) -> list:
    """
    메인 헤더 행과 서브헤더 행을 합쳐 실제 컬럼명 목록을 구성한다.
    빈 셀은 서브헤더 값으로 채운다.
    """
    main_headers = [
        str(sheet.cell_value(header_row, c)).strip()
        for c in range(sheet.ncols)
    ]
    sub_headers = [
        str(sheet.cell_value(sub_header_row, c)).strip()
        for c in range(sheet.ncols)
    ]

    combined = []
    for main, sub in zip(main_headers, sub_headers):
        if main == "" and sub != "":
            combined.append(sub)
        elif main != "":
            combined.append(main)
        else:
            combined.append("")
    return combined


def _normalize_columns(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns=COL_ALIASES)
    df["공종"] = sheet_name
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = ""
    # 위험요인이 비어있는 행 제거 (헤더 잔재, 빈 행 등)
    df = df[df["위험요인"].astype(str).str.strip() != ""]
    df = df[df["위험요인"].astype(str).str.strip() != "nan"]
    extra_cols = [c for c in df.columns if c not in REQUIRED_COLS]
    return df[REQUIRED_COLS + extra_cols]


def parse_xls_to_xlsx(xls_path: str, output_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb_xls = xlrd.open_workbook(xls_path)
    writer = pd.ExcelWriter(output_path, engine="openpyxl")

    processed = 0
    for sheet_name in wb_xls.sheet_names():
        if sheet_name in SKIP_SHEETS:
            continue
        sheet = wb_xls.sheet_by_name(sheet_name)
        if sheet.nrows < 2:
            continue

        header_row, sub_header_row = _find_header_rows(sheet)
        columns = _build_column_names(sheet, header_row, sub_header_row)

        # 데이터 행은 서브헤더 다음 행부터
        data_start = sub_header_row + 1
        rows = []
        for row_idx in range(data_start, sheet.nrows):
            row = [sheet.cell_value(row_idx, c) for c in range(sheet.ncols)]
            rows.append(row)

        if not rows:
            continue

        df = pd.DataFrame(rows, columns=columns)
        df = _normalize_columns(df, sheet_name)

        # Excel 시트명 최대 31자 제한
        safe_name = sheet_name[:31]
        df.to_excel(writer, sheet_name=safe_name, index=False)
        processed += 1

    writer.close()
    print(f"변환 완료: {output_path} ({processed}개 시트)")


if __name__ == "__main__":
    xls = sys.argv[1] if len(sys.argv) > 1 else "/Users/kimmiso/Desktop/위험성평가 모델/최초위험성평가 기초자료-건축_REV1.xls"
    out = sys.argv[2] if len(sys.argv) > 2 else "data/source/risk_db.xlsx"
    parse_xls_to_xlsx(xls, out)
