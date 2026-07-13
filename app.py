import glob
import pandas as pd

# 1. Otomatis mencari file Excel yang berawalan 'STOCK OPNAME' di folder yang sama
excel_files = glob.glob("STOCK OPNAME*.xlsx")

if not excel_files:
    print("❌ File Excel Stock Opname tidak ditemukan di folder ini!")
    exit()

# Mengambil file pertama yang dideteksi oleh glob
file_path = excel_files[0]
print(f"📂 Menggunakan file: {file_path}\n")

xls = pd.ExcelFile(file_path)

# 2. Cari semua sheet yang mengandung kata 'DATA' secara dinamis
data_sheets = [sheet for sheet in xls.sheet_names if 'DATA' in sheet.upper()]

for sheet in data_sheets:
    print(f"=== Memproses Pasangan untuk Sheet: {sheet} ===")
    df = pd.read_excel(file_path, sheet_name=sheet)
    
    # Standardisasi nama kolom (menghilangkan spasi berlebih)
    df.columns = df.columns.str.strip()
    
    # Pastikan kolom mandatory ada di sheet ini
    required_cols = {'PN', 'BIN', 'Result'}
    if not required_cols.issubset(df.columns):
        print(f"⚠️ Kolom {required_cols} tidak lengkap di sheet {sheet}. Skipping...")
        continue
        
    # Pembersihan string data dari spasi luar
    df['PN'] = df['PN'].astype(str).str.strip()
    df['BIN'] = df['BIN'].astype(str).str.strip()
    df['Result'] = df['Result'].astype(str).str.strip().str.upper()
    
    # 3. Filter data hanya untuk kategori discrepancy yang dicari
    target_results = {'SURPLUS', 'MINUS', 'NOT FOUND', 'UNRECORD', 'UNRECORDED', 'FOUND'}
    df_filtered = df[df['Result'].isin(target_results)].copy()
    
    # 4. Kelompokkan berdasarkan Part Number (PN) untuk mencari pasangan
    matched_pairs = []
    for pn, group in df_filtered.groupby('PN'):
        results_in_group = set(group['Result'])
        
        # Logika Pasangan antar discrepancy
        has_surplus_minus = 'SURPLUS' in results_in_group and 'MINUS' in results_in_group
        has_surplus_found = 'SURPLUS' in results_in_group and any(r in results_in_group for r in ['NOT FOUND', 'FOUND'])
        has_unrec_notfound = any(r in results_in_group for r in ['UNRECORD', 'UNRECORDED']) and any(r in results_in_group for r in ['NOT FOUND', 'FOUND'])
        has_unrec_minus    = any(r in results_in_group for r in ['UNRECORD', 'UNRECORDED']) and 'MINUS' in results_in_group
        
        # Jika masuk kriteria pasangan, ambil semua baris yang terikat dengan PN tersebut
        if has_surplus_minus or has_surplus_found or has_unrec_notfound or has_unrec_minus:
            for _, row in group.iterrows():
                matched_pairs.append({
                    'PN': row['PN'],
                    'BIN': row['BIN'],
                    'Result': row['Result'],
                    'Qty eMRO': row.get('Qty eMRO', row.get('QTY Available', '-')),
                    'Qty Actual': row.get('Qty Actual', '-')
                })
                
    # 5. Tampilkan Hasil Akhir per Sheet dalam format tabel bersih
    if matched_pairs:
        df_result = pd.DataFrame(matched_pairs)
        print(df_result.to_string(index=False))
    else:
        print("❌ Tidak ditemukan pasangan matching discrepancy pada sheet ini.")
    print("\n" + "="*50 + "\n")
