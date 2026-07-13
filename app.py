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
st.write("Versi Pembersihan Total: Memfilter komplain kosong, mengatasi typo penulisan, dan menampilkan Jenis Finding.")

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

# Fungsi internal mengekstrak teks penyelesaian dari chat secara cerdas
def extract_clean_evidence(clean_text):
    lines = clean_text.split("\n")
    
    # 1. Cari baris PENYELESAIAN (mentolerir typo seperti PENYELSAIAN)
    for idx, line in enumerate(lines):
        if re.search(r'PENYEL[E]*SAIAN', line, re.IGNORECASE) or any(k in line.upper() for k in ["COMPLETED", "COMPLITED", "DONE SIGNED"]):
            if ":" in line:
                evidence = line.split(":", 1)[-1].strip()
                remaining_lines = [l.strip() for l in lines[idx+1:] if l.strip()]
                if remaining_lines:
                    evidence += " | " + " | ".join(remaining_lines)
                return evidence
            else:
                # Jika format bintang tanpa titik dua (*PENYELSAIAN ALREADY ISSUED...*)
                evidence_lines = [l.strip() for l in lines[idx:] if l.strip()]
                return " | ".join(evidence_lines)
                
    # 2. Jika tidak ada penanda penyelesaian di atas, ambil baris non-identitas terbawah sebagai bukti kalimat bebas
    meaningful_lines = []
    for line in lines:
        l_upper = line.upper()
        # Abaikan baris identitas utama agar tidak menarik data mentah komplain
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
    
    # HANYA meloloskan kata kunci aksi penyelesaian nyata (Menghapus 'minus', 'surplus', 'not found')
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
                
                # Cek apakah ini murni chat komplain/finding awal tanpa aksi penyelesaian
                # Jika mengandung kata "remarks: minus" atau "remarks: not found" tapi TIDAK ADA kata kunci solusi, lewati.
                has_solusi_keyword = any(k in text_lower for k in keywords_valid_solusi)
                has_typo_penyelesaian = bool(re.search(r'PENYEL[E]*SAIAN', text_lower))
                
                if not (has_solusi_keyword or has_typo_penyelesaian):
                    continue
                
                pns_found = re.findall(r'(?:PN|ALT)\s*:\s*([^\n\s\r]+)|(?:PN|ALT)\s+([^\n\s\r:]+)', clean_text, re.IGNORECASE)
                flattened_pns = []
                for p1, p2 in pns_found:
                    p_val = p1 if p1 else p2
                    if p_val:
                        flattened_pns.append(p_val.strip().lower())
                
                if not flattened_pns:
                    words = re.findall(r'\b(MS\d+-\d+|BACP\w+|BACS\w+)\b', clean_text, re.IGNORECASE)
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
            
        def get_evidence_combo(row_data):
            pn_str = str(row_data['PN']).strip().lower()
            bin_str = str(row_data['BIN']).strip().lower() if 'BIN' in df_open.columns else ""
            
            if (pn_str, bin_str) in wa_combo_evidence:
                return wa_combo_evidence[(pn_str, bin_str)]
            elif (pn_str, "generic") in wa_combo_evidence:
                return wa_combo_evidence[(pn_str, "generic")]
            return "-"
            
        df_open['Asal_Sheet'] = sheet
        df_open['Pembelaan WhatsApp Lapangan'] = df_open.apply(get_evidence_combo, axis=1)
        
        # Buang data yang tidak mendapatkan pembelaan valid dari WA
        df_open = df_open[df_open['Pembelaan WhatsApp Lapangan'] != "-"].copy()
        
        # Tambahkan pemetaan jenis finding dari kolom Result/Remark/Diff asal excel
        if 'Result' in df_open.columns:
            df_open['Jenis Finding'] = df_open['Result']
        elif 'Remark' in df_open.columns:
            df_open['Jenis Finding'] = df_open['Remark']
        else:
            df_open['Jenis Finding'] = df_open['Diff'].apply(lambda x: 'MINUS' if x < 0 else ('SURPLUS' if x > 0 else 'DISCREPANCY'))
            
        if not df_open.empty:
            # Menyusun kolom sesuai permintaan: Asal_Sheet, Jenis Finding, PN, BIN, Qty eMRO, Qty Actual, Diff, Status, Pembelaan
            target_cols = ['Asal_Sheet', 'Jenis Finding', 'PN', 'BIN', 'Qty eMRO', 'Qty Actual', 'Diff', 'Status', 'Pembelaan WhatsApp Lapangan']
            valid_cols = [c for c in target_cols if c in df_open.columns]
            all_reconciled_dfs.append(df_open[valid_cols])
        
    df_final = pd.concat(all_reconciled_dfs, ignore_index=True) if all_reconciled_dfs else pd.DataFrame()
    return total_chat_in_range, df_final

if wa_file is not None and excel_file is not None:
    with st.spinner("Sedang membersihkan sampah data & menyelaraskan pembelaan... Mohon tunggu..."):
        total_chats, df_final_open = process_whatsapp_and_excel(
            wa_file.getvalue(), 
            excel_file.getvalue(), 
            start_dt, 
            end_dt
        )
        
    st.info(f"🔹 Hasil Scan WhatsApp: Ditemukan {total_chats} balon chat di dalam rentang tanggal pilihan.")
    
    if not df_final_open.empty:
        st.success(f"🎯 Berhasil merangkum {len(df_final_open)} baris temuan OPEN ber-pembelaan valid (Bebas dari noise komplain awal)!")
        
        st.markdown("### 📊 Preview Rekonsiliasi Bersih (Hanya Data Ber-Solusi)")
        st.dataframe(df_final_open, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_final_open.to_excel(writer, index=False, sheet_name='Pembelaan_Valid_Clean')
            
        st.markdown("### 📥 Download Hasil Rekap Data Open Ter-Filter")
        st.download_button(
            label="📊 Download Excel Rekonsiliasi Super Bersih (.xlsx)",
            data=buffer.getvalue(),
            file_name="hasil_rekonsiliasi_pembelaan_so_open_perfect.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning("⚠️ Tidak ada data 'OPEN' yang memiliki pembelaan/solusi valid di WhatsApp pada rentang tanggal tersebut.")
else:
    st.info("👋 Silakan upload file Excel Stock Opname dan file TXT Chat WhatsApp lo di atas untuk memulai.")
