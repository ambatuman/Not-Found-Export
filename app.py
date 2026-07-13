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
st.write("Versi Anti-Data-Purba: Prioritas Sheet Akurat & Karantina Duplikasi Status OPEN.")

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

def extract_clean_evidence(clean_text):
    lines = clean_text.split("\n")
    for idx, line in enumerate(lines):
        if re.search(r'PENYEL[E]*SAIAN', line, re.IGNORECASE) or any(k in line.upper() for k in ["COMPLETED", "COMPLITED", "DONE SIGNED"]):
            if ":" in line:
                evidence = line.split(":", 1)[-1].strip()
                remaining_lines = [l.strip() for l in lines[idx+1:] if l.strip()]
                if remaining_lines:
                    evidence += " | " + " | ".join(remaining_lines)
                return evidence
            else:
                evidence_lines = [l.strip() for l in lines[idx:] if l.strip()]
                return " | ".join(evidence_lines)
                
    meaningful_lines = []
    for line in lines:
        l_upper = line.upper()
        if any(hdr in l_upper for hdr in ["LOC:", "BIN:", "PN:", "SN:", "QTY EMRO:", "QTY ACT:", "REMARKS:", "QTY:"]):
            continue
        if line.strip():
            meaningful_lines.append(line.strip())
            
    if meaningful_lines:
        return " | ".join(meaningful_lines)
        
    return clean_text.replace('\n', ' | ')

@st.cache_data
def process_whatsapp_and_excel(wa_bytes, excel_bytes, start_dt, end_dt):
    # 1. PARSING WHATSAPP CHAT
    wa_string = wa_bytes.decode("utf-8")
    message_blocks = re.split(r'(?=\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*)', wa_string)
    
    wa_combo_evidence = {}
    total_chat_in_range = 0
    
    keywords_valid_solusi = [
        "found", "rts", "match", "issued", "transfer", "pindah", 
        "done", "solved", "terpasang", "di rcm", "di cs", "bagus", "✅",
        "complete", "complited", "penyelsayan", "penyelsian"
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
                
                if not (any(k in text_lower for k in keywords_valid_solusi) or re.search(r'PENYEL[E]*SAIAN', text_lower)):
                    continue
                
                pns_found = re.findall(r'(?:PN|ALT)\s*:\s*([^\n\s\r]+)|(?:PN|ALT)\s+([^\n\s\r:]+)', clean_text, re.IGNORECASE)
                flattened_pns = []
                for p1, p2 in pns_found:
                    p_val = p1 if p1 else p2
                    if p_val:
                        flattened_pns.append(p_val.strip().lower())
                
                if not flattened_pns:
                    words = re.findall(r'\b(MS\d+-\d+|BACP\w+|BACS\w+|NSA\w+-\w+)\b', clean_text, re.IGNORECASE)
                    flattened_pns = [w.strip().lower() for w in words]
                
                bin_match = re.search(r'BIN\s*:\s*([^\n\s\r]+)|BIN\s+([^\n\s\r:]+)', clean_text, re.IGNORECASE)
                bin_clean = ""
                if bin_match:
                    bin_val = bin_match.group(1) if bin_match.group(1) else bin_match.group(2)
                    if bin_val:
                        bin_clean = bin_val.strip().lower()
                
                if flattened_pns:
                    extracted_text = extract_clean_evidence(clean_text)
                    evidence_str = f"[{sender}] -> {extracted_text}"
                    
                    for pn_clean in flattened_pns:
                        if len(pn_clean) > 3:
                            if bin_clean:
                                wa_combo_evidence[(pn_clean, bin_clean)] = evidence_str
                            else:
                                wa_combo_evidence[(pn_clean, "generic")] = evidence_str

    # 2. BACA & URUTKAN SHEET EXCEL SECARA CERDAS
    xls = pd.ExcelFile(io.BytesIO(excel_bytes))
    raw_sheets = xls.sheet_names
    
    # Kelompokkan prioritas: Worksheet utama didahulukan, sheet 'OLD/PREV' ditaruh paling belakang
    sorted_sheets = []
    worksheets_main = [s for s in raw_sheets if s.lower() == 'worksheet']
    data_sheets = [s for s in raw_sheets if 'DATA' in s.upper() and s.lower() != 'worksheet']
    other_sheets = [s for s in raw_sheets if s.lower() != 'worksheet' and 'DATA' not in s.upper() and 'OLD' not in s.upper() and 'PREV' not in s.upper()]
    old_sheets = [s for s in raw_sheets if 'OLD' in s.upper() or 'PREV' in s.upper()]
    
    sorted_sheets = worksheets_main + data_sheets + other_sheets + old_sheets
    
    all_reconciled_dfs = []
    # Set pelacak combo (PN + BIN) yang sudah sukses ditutup di sheet utama
    closed_combos = set()
    
    for sheet in sorted_sheets:
        df_master = pd.read_excel(xls, sheet_name=sheet)
        df_master.columns = df_master.columns.str.strip()
        
        if 'Status' not in df_master.columns or 'PN' not in df_master.columns:
            continue
            
        # Catat combo PN + BIN yang status riilnya sudah CLOSED / MATCHED di sheet utama agar sheet jadul tidak lolos
        df_non_open = df_master[df_master['Status'].astype(str).str.strip().str.upper().isin(['CLOSED', 'MATCHED'])].copy()
        for _, r_non in df_non_open.iterrows():
            pn_k = str(r_non['PN']).strip().lower()
            bin_k = str(r_non['BIN']).strip().lower() if 'BIN' in df_master.columns else ""
            closed_combos.add((pn_k, bin_k))
            
        df_open = df_master[df_master['Status'].astype(str).str.strip().str.upper() == 'OPEN'].copy()
        if df_open.empty:
            continue
            
        def get_evidence_combo(row_data):
            pn_str = str(row_data['PN']).strip().lower()
            bin_str = str(row_data['BIN']).strip().lower() if 'BIN' in df_open.columns else ""
            
            # Jika baris ini datang dari sheet cadangan lama TAPI di data master utama dia sudah closed/matched, blokir!
            if (pn_str, bin_str) in closed_combos and ('OLD' in sheet.upper() or 'PREV' in sheet.upper()):
                return "-"
                
            if (pn_str, bin_str) in wa_combo_evidence:
                return wa_combo_evidence[(pn_str, bin_str)]
            elif (pn_str, "generic") in wa_combo_evidence:
                return wa_combo_evidence[(pn_str, "generic")]
            return "-"
            
        df_open['Asal_Sheet'] = sheet
        df_open['Pembelaan WhatsApp Lapangan'] = df_open.apply(get_evidence_combo, axis=1)
        
        df_open = df_open[df_open['Pembelaan WhatsApp Lapangan'] != "-"].copy()
        
        if 'Result' in df_open.columns:
            df_open['Jenis Finding'] = df_open['Result']
        elif 'Remark' in df_open.columns:
            df_open['Jenis Finding'] = df_open['Remark']
        else:
            df_open['Jenis Finding'] = df_open['Diff'].apply(lambda x: 'MINUS' if x < 0 else ('SURPLUS' if x > 0 else 'DISCREPANCY'))
            
        if 'SN' in df_open.columns:
            df_open['SN'] = df_open['SN'].fillna('-').astype(str).str.strip()
            
        if not df_open.empty:
            target_cols = ['Asal_Sheet', 'PN', 'SN', 'BIN', 'Qty eMRO', 'Qty Actual', 'Diff', 'Jenis Finding', 'Status', 'Pembelaan WhatsApp Lapangan']
            valid_cols = [c for c in target_cols if c in df_open.columns]
            all_reconciled_dfs.append(df_open[valid_cols])
        
    df_final = pd.concat(all_reconciled_dfs, ignore_index=True) if all_reconciled_dfs else pd.DataFrame()
    return total_chat_in_range, df_final

if wa_file is not None and excel_file is not None:
    with st.spinner("Sedang memproses penyelarasan urutan prioritas data... Mohon tunggu..."):
        total_chats, df_final_open = process_whatsapp_and_excel(
            wa_file.getvalue(), 
            excel_file.getvalue(), 
            start_dt, 
            end_dt
        )
        
    st.info(f"🔹 Hasil Scan WhatsApp: Ditemukan {total_chats} balon chat di dalam rentang tanggal pilihan.")
    
    if not df_final_open.empty:
        st.success(f"🎯 Berhasil merangkum {len(df_final_open)} baris temuan OPEN valid bebas dari gangguan duplikasi data!")
        
        st.markdown("### 📊 Preview Rekonsiliasi Hasil Urutan Cerdas")
        st.dataframe(df_final_open, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_final_open.to_excel(writer, index=False, sheet_name='Hasil_Rekonsil_Fix')
            
        st.markdown("### 📥 Download Hasil Rekap Data Open Ter-Update")
        st.download_button(
            label="📊 Download Excel Bebas Duplikasi Jamin Akurat (.xlsx)",
            data=buffer.getvalue(),
            file_name="hasil_rekonsiliasi_pembelaan_perfect_v3.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning("⚠️ Tidak ada kecocokan data 'OPEN' yang memiliki pembelaan/solusi valid di WhatsApp pada rentang tanggal tersebut.")
else:
    st.info("👋 Silakan upload file Excel Stock Opname dan file TXT Chat WhatsApp lo di atas untuk memulai.")
