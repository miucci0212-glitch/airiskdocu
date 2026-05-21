import openpyxl
import hashlib

def _krc_doc_text(unit_work: str, sub_work: str, hazard: str, accident: str) -> str:
    return (
        f"[단위작업]{unit_work} "
        f"[세부단위작업]{sub_work} "
        f"[유해위험요인]{hazard} "
        f"[재해유형]{accident}"
    )

def main():
    xlsx_path = "/Users/kimmiso/Desktop/위험성평가 모델/KRC/자체 유해·위험요인 DB.xlsx"
    print("Loading workbook...")
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb.active
    print("Workbook loaded.")

    seen_ids = set()
    total = 0
    current = None
    
    def emit(group):
        nonlocal total
        key = "|".join([
            "krc",
            group["project"], group["work"], group["unit_work"], group["sub_work"],
            str(group["no"]), group["hazard"], group["accident"],
        ])
        doc_id = hashlib.md5(key.encode()).hexdigest()
        if doc_id in seen_ids:
            return  # skip exact duplicate
        seen_ids.add(doc_id)
        
        controls_joined = " | ".join([c for c in group["controls"] if c])
        doc_text = _krc_doc_text(
            group["unit_work"], group["sub_work"], group["hazard"], group["accident"]
        )
        total += 1

    try:
        for r_idx, raw in enumerate(ws.iter_rows(min_row=4, values_only=True)):
            no_cell = raw[0]
            if no_cell is None and not any(raw):
                continue
            is_new = isinstance(no_cell, (int, float))
            if is_new:
                if current is not None:
                    emit(current)
                current_no = int(no_cell)
                current = {
                    "no": current_no,
                    "project": str(raw[1] or "").strip(),
                    "work": str(raw[2] or "").strip(),
                    "unit_work": str(raw[3] or "").strip(),
                    "sub_work": str(raw[4] or "").strip(),
                    "hazard": str(raw[5] or "").strip(),
                    "accident": str(raw[6] or "").strip(),
                    "controls": [str(raw[7] or "").strip()],
                    "laws": str(raw[8] or "").strip(),
                    "permit": str(raw[9] or "").strip(),
                }
            else:
                if current is None:
                    continue  # leading "-" before any numbered row — skip
                extra = str(raw[7] or "").strip()
                if extra:
                    current["controls"].append(extra)
                    
            if r_idx % 10000 == 0 and r_idx > 0:
                print(f"Processed {r_idx} rows, total groups: {total}")
                
        if current is not None:
            emit(current)
            
        print(f"Success! Total groups: {total}")
    except Exception as e:
        print(f"Error at row index {r_idx + 4}: {e}")

if __name__ == "__main__":
    main()
