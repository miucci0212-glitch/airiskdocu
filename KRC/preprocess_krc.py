import openpyxl
import json
import os

def clean_text(text):
    if text is None:
        return ""
    # Strip whitespace and normalize
    return str(text).strip()

def preprocess():
    xlsx_path = "/Users/kimmiso/Desktop/위험성평가 모델/KRC/자체 유해·위험요인 DB.xlsx"
    output_path = "/Users/kimmiso/Desktop/위험성평가 모델/webapp/backend/data/source/krc_risk_db_cleaned.json"
    
    print(f"Loading Excel file: {xlsx_path}...", flush=True)
    if not os.path.exists(xlsx_path):
        print(f"Error: Excel file not found at {xlsx_path}", flush=True)
        return
        
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb.active
    print(f"Workbook loaded. Active sheet: {ws.title}", flush=True)
    
    groups = []
    current = None
    row_count = 0
    
    print("Starting processing...", flush=True)
    for idx, raw in enumerate(ws.iter_rows(min_row=4, values_only=True)):
        row_count += 1
        no_cell = raw[0]
        
        # If the entire row is empty, skip
        if no_cell is None and not any(raw):
            continue
            
        is_new = isinstance(no_cell, (int, float))
        
        if is_new:
            if current is not None:
                groups.append(current)
            current_no = int(no_cell)
            current = {
                "no": current_no,
                "project": clean_text(raw[1]),
                "work": clean_text(raw[2]),
                "unit_work": clean_text(raw[3]),
                "sub_work": clean_text(raw[4]),
                "hazard": clean_text(raw[5]),
                "accident": clean_text(raw[6]),
                "controls": [clean_text(raw[7])] if clean_text(raw[7]) else [],
                "laws": clean_text(raw[8]),
                "permit": clean_text(raw[9]),
                "major_accident": clean_text(raw[10]) if len(raw) > 10 else "",
                "accident_case": clean_text(raw[11]) if len(raw) > 11 else "",
                "near_miss": clean_text(raw[12]) if len(raw) > 12 else "",
                "sif": clean_text(raw[13]) if len(raw) > 13 else "",
                "profile": clean_text(raw[14]) if len(raw) > 14 else ""
            }
        else:
            if current is None:
                continue # Leading "-" or invalid rows before any numbered row
            
            control_val = clean_text(raw[7])
            if control_val and control_val not in current["controls"]:
                current["controls"].append(control_val)
                
            # If laws, permit or other fields are missing in the main row but present in the sub-row, backfill them
            if not current["laws"] and len(raw) > 8 and raw[8]:
                current["laws"] = clean_text(raw[8])
            if not current["permit"] and len(raw) > 9 and raw[9]:
                current["permit"] = clean_text(raw[9])
                
        if row_count % 10000 == 0:
            print(f"Processed {row_count} rows, found {len(groups)} groups...", flush=True)

    if current is not None:
        groups.append(current)
        
    print(f"Processing finished. Total rows processed: {row_count}. Total groups found: {len(groups)}.", flush=True)
    
    # Save to JSON
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"Saving preprocessed data to {output_path}...", flush=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)
    print("Save completed successfully!", flush=True)

if __name__ == "__main__":
    preprocess()
