import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime

st.set_page_config(
    page_title="WhatsApp Audit Reconciler - Pure Precision Engine",
    page_icon="📊",
    layout="wide"
)

st.title("📊 WhatsApp Audit Reconciler (Pure Precision Engine)")
st.write("Versi Super Kilat & Cerdas: Pengecekan instan dengan ekstraksi otomatis baris *PENYELESAIAN*.")

st.divider()

# --- PILIHAN FILTER TANGGAL ---
st.sidebar.header("📅 Pengaturan Filter Tanggal Chat")
start_date = st.sidebar.date_input("Tanggal Awal Chat:", value=datetime(2026, 6, 1))
end_date = st.sidebar.date_input("Tanggal Akhir Chat:", value=datetime(2026, 7, 13))

start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 1️⃣ File Txt WhatsApp")
    wa_file = st.file_uploader("Upload file chat WhatsApp (.txt):", type=["txt"])

with col2:
    st.markdown("### 2️⃣ File Excel Audit Master")
    excel_file = st.file_uploader("Upload Master Excel Stock Take (.xlsx):", type=["xlsx"])

# Fungsi internal untuk memotong teks bukti penyelesaian secara cerdas
def extract_clean_evidence(clean_text):
    lines = clean_text.split("\n")
    
    # 1. Prioritas Utama: Cari kata PENYELESAIAN terlebih dahulu
    for idx, line in enumerate(lines):
        if "PENYELESAIAN" in line.upper():
            if ":" in line:
                evidence = line.split(":", 1)[-1].strip()
                remaining_lines = [l.strip() for l in lines[idx+1:] if l.strip()]
                if remaining_lines:
                    evidence += " | " + " | ".join(remaining_lines)
                return evidence
            else:
                # Menangani format tanpa titik dua seperti *PENYELESAIAN PENDING ISSUED DONE...*
                evidence_lines = [l.strip() for l in lines[idx:] if l.strip()]
                return " | ".join(evidence_lines)
                
    # 2. Prioritas Kedua: Jika tidak ada kata PENYELESAIAN, baru ambil kata REMARK
    for idx, line in enumerate(lines):
        if any(r in line.upper() for r in ["REMARK", "REMAKS"]) and ":" in line:
            return line.split(":", 1)[-1].strip()
            
    # 3. Fallback: Jika tidak ada format teratur, ambil seluruh baris chat dipisah pipa
    return clean_text.replace('\n', ' | ')

# Fungsi komputasi utama ter-cache agar loading instant
@st.cache_data
def process_whatsapp_and_excel(wa_bytes, excel_bytes, start_dt, end_dt):
    # 1. PARSING WHATSAPP CHAT
    wa_string = wa_bytes.decode("utf-8")
    message_blocks = re.split(r'(?=\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*)', wa_string)
    
    wa_indexed_evidence = {}
    total_chat_in_range = 0
    
    keywords_valid_solusi = [
        "found", "rts", "match", "issued", "transfer", "pindah", 
        "done", "solved", "terpasang", "di rcm", "di cs", "bagus", "✅",
        "penyele", "penyelesaian"
    ]
    
    for block in message_blocks:
        if not block.strip():
            continue
            
        time_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2})', block.strip())
        if time_match:
            date_str = time_match.group(1)
            for fmt in ("%m/%d/%y", "%m/%d/%Y", "%d/%m/%y", "%d/%m/%Y"):
                try:
                    msg_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    msg_date = None
            
            if msg_date and (start_dt <= msg_date <= end_dt):
                total_chat_in_range += 1
                
                clean_text = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*[^:]+:\s*', '', block, flags=re.IGNORECASE).strip()
                meta_match = re.match(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*([^:]+):', block.strip())
                sender = meta_match.group(1).strip() if meta_match else "Store Lapangan"
                
                text_lower = clean_text.lower()
                pns_found = re.findall(r'PN\s*:\s*([^\n\s\r]+)', clean_text, re.IGNORECASE)
                
                # Validasi apakah balon chat mengandung penyelesaian valid
                if any(k in text_lower for k in keywords_valid_solusi):
                    extracted_text = extract_clean_evidence(clean_text)
                    evidence_str = f"[{sender}] -> {extracted_text}"
                    
                    for pn in pns_found:
                        pn_clean = pn.strip().lower()
                        if len(pn_clean) > 3:
                            wa_indexed_evidence[pn_clean] = evidence_str

    # 2. BACA DATA MASTER EXCEL AUDIT
    xls = pd.ExcelFile(io.BytesIO(excel_bytes))
    data_sheets = [sheet for sheet in xls.sheet_names if 'DATA' in sheet.upper()]
    if not data_sheets:
        data_sheets = [xls.sheet_names[0]]
        
    all_reconciled_dfs = []
    
    for sheet in data_sheets:
        df_master = pd.read_excel(xls, sheet_name=sheet)
        df_master.columns = df_master.columns.str.strip()
        
        if 'Status' not in df_master.columns or 'PN' not in df_master.columns:
            continue
            
        df_open = df_master[df_master['Status'].astype(str).str.strip().str.upper() == 'OPEN'].copy()
        if df_open.empty:
            continue
            
        def get_evidence(pn_val):
            pn_str = str(pn_val).strip().lower()
            return wa_indexed_evidence.get(pn_str, "-")
            
        df_open['Asal_Sheet'] = sheet
        df_open['Pembelaan WhatsApp Lapangan'] = df_open['PN'].apply(get_evidence)
        all_reconciled_dfs.append(df_open)
        
    df_final = pd.concat(all_reconciled_dfs, ignore_index=True) if all_reconciled_dfs else pd.DataFrame()
    return total_chat_in_range, df_final

if wa_file is not None and excel_file is not None:
    with st.spinner("Sedang menyinkronkan data dengan metode cepat... Mohon tunggu..."):
        total_chats, df_final_open = process_whatsapp_and_excel(
            wa_file.getvalue(), 
            excel_file.getvalue(), 
            start_dt, 
            end_dt
        )
        
    st.info(f"🔹 Hasil Scan WhatsApp: Ditemukan {total_chats} balon chat di dalam rentang tanggal pilihan.")
    
    if not df_final_open.empty:
        st.success(f"🎯 Berhasil memproses total {len(df_final_open)} baris temuan berstatus OPEN dari seluruh sheet data!")
        
        st.markdown("### 📊 Preview Hasil Sinkronisasi Data OPEN vs WhatsApp")
        
        preview_cols = ['Asal_Sheet', 'PN', 'BIN', 'Status', 'Pembelaan WhatsApp Lapangan']
        if 'No' in df_final_open.columns: preview_cols.insert(1, 'No')
        if 'Qty eMRO' in df_final_open.columns: preview_cols.append('Qty eMRO')
        if 'Qty Actual' in df_final_open.columns: preview_cols.append('Qty Actual')
        
        actual_preview_cols = [c for c in preview_cols if c in df_final_open.columns]
        st.dataframe(df_final_open[actual_preview_cols], use_container_width=True)
        
        # Ekspor ke bytes excel untuk tombol unduh
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_final_open.to_excel(writer, index=False, sheet_name='Hasil_Rekonsiliasi_Open')
            
        st.markdown("### 📥 Download Hasil Rekap Data Open Terupdate")
        st.download_button(
            label="📊 Download Excel Pembelaan Ter-Reconcile (.xlsx)",
            data=buffer.getvalue(),
            file_name="hasil_rekonsiliasi_pembelaan_so_open.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning("⚠️ Tidak ada data berstatus 'OPEN' yang terdeteksi atau kecocokan yang valid.")
else:
    st.info("👋 Silakan upload file Excel Stock Opname dan file TXT Chat WhatsApp lo di atas untuk memulai.")
