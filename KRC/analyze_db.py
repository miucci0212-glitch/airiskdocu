import openpyxl
import sys

def main():
    xlsx_path = "/Users/kimmiso/Desktop/위험성평가 모델/KRC/자체 유해·위험요인 DB.xlsx"
    print("Loading workbook...", flush=True)
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb.active
    print(f"Active sheet: {ws.title}", flush=True)
    
    total_rows = 0
    numbered_rows = 0
    dash_rows = 0
    other_rows = 0
    
    # We will also count how many groups we would form
    current_no = None
    group_count = 0
    control_counts = []
    current_controls = 0
    
    for idx, raw in enumerate(ws.iter_rows(min_row=4, values_only=True)):
        total_rows += 1
        no_cell = raw[0]
        
        if no_cell is None and not any(raw):
            continue
            
        if isinstance(no_cell, (int, float)):
            numbered_rows += 1
            if current_controls > 0:
                control_counts.append(current_controls)
            group_count += 1
            current_controls = 1 if raw[7] else 0
        elif str(no_cell).strip() == '-':
            dash_rows += 1
            if raw[7]:
                current_controls += 1
        else:
            other_rows += 1
            
        if idx < 10:
            print(f"Row {idx+4}: No={no_cell}, project={raw[1]}, work={raw[2]}, unit={raw[3]}, sub={raw[4]}, hazard={raw[5][:20] if raw[5] else None}, control={raw[7][:20] if raw[7] else None}")

    if current_controls > 0:
        control_counts.append(current_controls)
        
    print("\n--- Statistics ---")
    print(f"Total rows parsed (from row 4): {total_rows}")
    print(f"Numbered rows (new groups): {numbered_rows}")
    print(f"Dash rows (-): {dash_rows}")
    print(f"Other rows: {other_rows}")
    print(f"Total groups formed: {group_count}")
    if control_counts:
        print(f"Avg controls per group: {sum(control_counts)/len(control_counts):.2f}")
        print(f"Max controls in a group: {max(control_counts)}")
        print(f"Min controls in a group: {min(control_counts)}")

if __name__ == "__main__":
    main()
