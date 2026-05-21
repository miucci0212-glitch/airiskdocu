"""농어촌공사 위험성평가 양식 채우기."""
import os
import shutil
import copy
from datetime import date
from typing import Optional

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from models import KrcMetadata, KrcRow


BODY_START_ROW = 10
ROWS_PER_ENTRY = 2
MAX_ENTRIES = 3


def _format_date(d: Optional[date]) -> str:
    if d is None:
        return ""
    return d.strftime("%Y. %m. %d.")


def _template_for(krc_type: str) -> str:
    return "krc_수시_template.xlsx" if krc_type == "수시" else "krc_초기정기_template.xlsx"


def copy_row_structure(ws, src_top: int, src_bot: int, dest_top: int, dest_bot: int):
    """기준이 되는 행(src_top, src_bot)의 스타일, 값, 셀 병합을 새 행(dest_top, dest_bot)으로 완벽 복제합니다."""
    max_col = ws.max_column
    for col in range(1, max_col + 1):
        for src_row, dest_row in [(src_top, dest_top), (src_bot, dest_bot)]:
            src_cell = ws.cell(row=src_row, column=col)
            dest_cell = ws.cell(row=dest_row, column=col)
            
            # 셀 스타일 복제
            if src_cell.has_style:
                dest_cell.font = copy.copy(src_cell.font)
                dest_cell.fill = copy.copy(src_cell.fill)
                dest_cell.border = copy.copy(src_cell.border)
                dest_cell.alignment = copy.copy(src_cell.alignment)
                dest_cell.number_format = copy.copy(src_cell.number_format)
                dest_cell.protection = copy.copy(src_cell.protection)
            
            # 특정 고정 기본값 복제 (예: 수시 템플릿 J열 "검토/추록" 등)
            if src_cell.value is not None:
                dest_cell.value = src_cell.value

    # 병합 정보 복제
    ranges_to_add = []
    for r in list(ws.merged_cells.ranges):
        # 만약 병합 범위가 기준 행 범위 내에 있다면
        if r.min_row >= src_top and r.max_row <= src_bot:
            row_diff_min = r.min_row - src_top
            row_diff_max = r.max_row - src_top
            
            new_min_row = dest_top + row_diff_min
            new_max_row = dest_top + row_diff_max
            
            new_range = f"{get_column_letter(r.min_col)}{new_min_row}:{get_column_letter(r.max_col)}{new_max_row}"
            ranges_to_add.append(new_range)
            
    for rng in ranges_to_add:
        try:
            ws.merge_cells(rng)
        except Exception:
            pass


def fill_krc_template(
    metadata: KrcMetadata,
    rows: list[KrcRow],
    template_dir: str,
    output_path: str,
) -> str:
    template_path = os.path.join(template_dir, _template_for(metadata.krc_type))
    shutil.copy2(template_path, output_path)
    wb = load_workbook(output_path)
    ws = wb.active

    ws["B1"] = metadata.site_name
    ws["B2"] = _format_date(metadata.write_date)
    ws["B4"] = metadata.approver_construction
    ws["B5"] = f"{_format_date(metadata.period_start)} ~ {_format_date(metadata.period_end)}"
    # B3, B6 are placeholder labels in the template ("(위험성평가 회의일 또는 이전)",
    # "(위험성평가 실시규정에 정해진 주기)") — leave them as-is.
    ws["M2"] = metadata.approver_construction
    ws["N2"] = metadata.approver_safety
    ws["O2"] = metadata.approver_site_manager
    ws["R2"] = metadata.inspector_supervisor

    # 만약 rows 개수가 기본 제공되는 MAX_ENTRIES(3)를 초과한다면 그만큼 행을 동적으로 삽입하고 레이아웃 복제
    extra_entries = len(rows) - MAX_ENTRIES
    if extra_entries > 0:
        insert_start = BODY_START_ROW + MAX_ENTRIES * ROWS_PER_ENTRY  # 10 + 3 * 2 = 16
        ws.insert_rows(insert_start, extra_entries * ROWS_PER_ENTRY)
        
        src_top = insert_start - 2  # 14
        src_bot = insert_start - 1  # 15
        
        for k in range(extra_entries):
            dest_top = insert_start + k * ROWS_PER_ENTRY
            dest_bot = dest_top + 1
            copy_row_structure(ws, src_top, src_bot, dest_top, dest_bot)

    # 모든 rows 기록 (MAX_ENTRIES 제한 제거)
    for i, row in enumerate(rows):
        top = BODY_START_ROW + i * ROWS_PER_ENTRY
        bot = top + 1
        ws[f"A{top}"] = row.detail_work or ""
        ws[f"A{bot}"] = row.work_location or ""
        ws[f"B{top}"] = row.equipment or ""
        ws[f"C{top}"] = row.hazard or ""
        ws[f"F{top}"] = row.accident_type or ""
        if row.frequency is not None:
            ws[f"G{top}"] = row.frequency
        if row.severity is not None:
            ws[f"H{top}"] = row.severity
        ws[f"I{top}"] = row.risk_grade or ""
        ws[f"J{top}"] = row.controls or ""
        ws[f"P{top}"] = row.improved_risk or ""
        ws[f"P{bot}"] = row.improvement_due or ""
        ws[f"R{top}"] = row.executor or ""
        ws[f"R{bot}"] = row.verifier or ""

    wb.save(output_path)
    return output_path

