import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime

st.set_page_config(
    page_title="WhatsApp Audit Reconciler - Auditee Evidence Engine",
    page_icon="📊",
    layout="wide"
)

st.title("📊 WhatsApp Audit Reconciler (Murni Pembelaan Auditee)")
st.write("Menyaring & menyajikan KHUSUS pembelaan/solusi dari Auditee (mengabaikan laporan temuan awal dari Auditor dan mencocokkan SN secara presisi).")

st.divider()

# --- PILIHAN FILTER TANGGAL ---
st.sidebar.header("📅 Pengaturan Filter Tanggal Chat")
start_date = st.sidebar.date_input("Tanggal Awal Chat:", value=datetime(2026, 6, 1))
end_date = st.sidebar.date_input("Tanggal Akhir Chat:", value=datetime(2026, 7, 31))

start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 1️⃣ File Txt WhatsApp")
    wa_file = st.file_uploader("Upload file chat WhatsApp (.txt):", type=["txt"])

with col2:
    st.markdown("### 2️⃣ File Excel Audit Master")
    excel_file = st.file_uploader("Upload Master Excel Stock Take (.xlsx):", type=["xlsx"])


def normalize_str(val):
    """Membersihkan spasi, tanda hubung, dan huruf besar/kecil untuk perbandingan akurat"""
    if not val or pd.isna(val):
        return ""
    res = re.sub(r'[^A-ZA-Z0-9]', '', str(val)).upper()
    if res in ['-', 'NONE', 'NAN', 'NA', 'NULL']:
        return ""
    return res


def extract_full_evidence(clean_text):
    """Mengambil seluruh pesan sebagai bukti tanpa memotong informasi penting"""
    lines = [l.strip() for l in str(clean_text).split("\n") if l.strip()]
    return " | ".join(lines)


def is_auditee_solution(clean_text):
    """
    FUNGSI PENYARING SUPER KETAT:
    Hanya meloloskan pesan yang MURNI mengandung kalimat/bukti penyelesaian dari Auditee.
    """
    text_upper = clean_text.upper()
    
    # Frasa negatif khas laporan/temuan Auditor
    negative_indicators = [
        r'NOT\s+COMPLETED', 
        r'UNDER\s+INVESTIGATE', 
        r'NOT\s+FOUND',
        r'REMARK[S]?\s*:\s*MINUS', 
        r'REMARK[S]?\s*:\s*SURPLUS', 
        r'REMARK[S]?\s*:\s*[\-\+]?\d+'
    ]
    
    # Kata kunci bukti/solusi riil dari Auditee
    solution_keywords = [
        "ALREADY FOUND", "HAS BEEN", "ISSUED", "WO:", "WO ", "T/C", "TASKCARD", "TASK CARD",
        "RTS", "MATCH TO", "MATCHED", "TRANSFER", "PINDAH", "TERPASANG", 
        "PENYELESAIAN", "PENYELSAYAN", "AFML", "MATSLIP"
    ]
    
    # Kata 'COMPLETED' hanya valid jika TIDAK diawali kata 'NOT'
    has_completed = bool(re.search(r'(?<!NOT\s)(?<!NOT\s\s)COMPLETED', text_upper)) or bool(re.search(r'(?<!NOT\s)COMPLITED', text_upper))
    has_other_solution = any(k in text_upper for k in solution_keywords)
    
    has_solution = has_completed or has_other_solution
    has_neg = any(re.search(p, text_upper) for p in negative_indicators)
    
    # Jika mengandung indikator negatif (misal: NOT COMPLETED) dan TANPA kata kunci solusi kuat -> ABAIKAN
    if has_neg and not has_solution:
        return False
        
    return has_solution


@st.cache_data
def process_whatsapp_and_excel(wa_bytes, excel_bytes, start_dt, end_dt):
    # 1. PARSING WHATSAPP CHAT
    wa_string = wa_bytes.decode("utf-8", errors="ignore")
    wa_string = wa_string.replace('\u202f', ' ').replace('\xa0', ' ')
    
    message_blocks = re.split(r'(?=\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}[,\s]+\d{1,2}:\d{2})', wa_string)
    
    wa_evidence_records = []
    total_chat_in_range = 0
    
    for block in message_blocks:
        if not block.strip():
            continue
            
        date_match = re.search(r'(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})', block)
        msg_date = None
        if date_match:
            d1, d2, y = date_match.group(1), date_match.group(2), date_match.group(3)
            if len(y) == 2:
                y = "20" + y
            for p1, p2 in [(d1, d2), (d2, d1)]:
                try:
                    dt_cand = datetime(int(y), int(p1), int(p2))
                    if datetime(2025, 1, 1) <= dt_cand <= datetime(2027, 12, 31):
                        msg_date = dt_cand
                        break
                except ValueError:
                    continue

        if msg_date and (start_dt <= msg_date <= end_dt):
            total_chat_in_range += 1
            
            clean_text = re.sub(r'^\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}.*?-\s*', '', block).strip()
            sender_match = re.match(r'^([^:]+):', clean_text)
            sender = sender_match.group(1).strip() if sender_match else "Auditee Lapangan"
            
            if not is_auditee_solution(clean_text):
                continue
            
            # Ekstrak LOC, BIN, SN, PN
            loc_match = re.search(r'LOC\s*:\s*([A-Za-z0-9\-_]+)', clean_text, re.IGNORECASE)
            loc_raw = loc_match.group(1) if loc_match else ""
            
            bin_match = re.search(r'BIN\s*:\s*([A-Za-z0-9\-_]+)', clean_text, re.IGNORECASE)
            bin_raw = bin_match.group(1) if bin_match else ""

            sn_match = re.search(r'SN\s*:\s*([A-Za-z0-9\-_]+)', clean_text, re.IGNORECASE)
            sn_raw = sn_match.group(1) if sn_match else ""

            pn_matches = re.findall(r'(?:PN|PART|ALT)\s*:\s*([A-Za-z0-9\-_]+)', clean_text, re.IGNORECASE)
            if not pn_matches:
                pn_matches = re.findall(r'\b([0-9A-Z]{3,}-[0-9A-Z\-]+)\b', clean_text, re.IGNORECASE)
            
            evidence_text = f"[{sender}] -> {extract_full_evidence(clean_text)}"
            
            if pn_matches:
                for pn in pn_matches:
                    pn_norm = normalize_str(pn)
                    bin_norm = normalize_str(bin_raw)
                    loc_norm = normalize_str(loc_raw)
                    sn_norm = normalize_str(sn_raw)
                    
                    if len(pn_norm) >= 3:
                        wa_evidence_records.append({
                            'pn_norm': pn_norm,
                            'bin_norm': bin_norm,
                            'loc_norm': loc_norm,
                            'sn_norm': sn_norm,
                            'evidence': evidence_text
                        })

    # 2. BACA FILE MASTER EXCEL AUDIT
    xls = pd.ExcelFile(io.BytesIO(excel_bytes))
    all_reconciled_dfs = []
    
    for sheet in xls.sheet_names:
        if sheet.upper() in ['SUMMARY', 'LOOKUP ANDIKA', 'LAST SO', 'PART STATUS MISSING']:
            continue
            
        df_raw = pd.read_excel(xls, sheet_name=sheet, header=None)
        header_row = 0
        
        for idx, row in df_raw.iterrows():
            row_str = [str(x).upper() for x in row.values if pd.notna(x)]
            if any('PN' in x for x in row_str) and any('STATUS' in x for x in row_str):
                header_row = idx
                break
                
        df_master = pd.read_excel(xls, sheet_name=sheet, header=header_row)
        df_master.columns = df_master.columns.astype(str).str.strip()
        
        pn_col = next((c for c in df_master.columns if 'PN' in c.upper() or 'PART' in c.upper()), None)
        status_col = next((c for c in df_master.columns if 'STATUS' in c.upper()), None)
        loc_col = next((c for c in df_master.columns if 'LOC' in c.upper() or 'LOCATION' in c.upper()), None)
        bin_col = next((c for c in df_master.columns if 'BIN' in c.upper()), None)
        sn_col = next((c for c in df_master.columns if 'SN' in c.upper() or 'SERIAL' in c.upper()), None)
        
        if not pn_col or not status_col:
            continue
            
        df_open = df_master[df_master[status_col].astype(str).str.strip().str.upper() == 'OPEN'].copy()
        if df_open.empty:
            continue
            
        def find_matching_wa(row):
            pn_val = normalize_str(row[pn_col])
            bin_val = normalize_str(row[bin_col]) if bin_col and pd.notna(row[bin_col]) else ""
            loc_val = normalize_str(row[loc_col]) if loc_col and pd.notna(row[loc_col]) else ""
            sn_val = normalize_str(row[sn_col]) if sn_col and pd.notna(row[sn_col]) else ""
            
            matched_evidences = []
            for record in wa_evidence_records:
                if record['pn_norm'] == pn_val:
                    bin_match_ok = not bin_val or not record['bin_norm'] or record['bin_norm'] == bin_val
                    loc_match_ok = not loc_val or not record['loc_norm'] or record['loc_norm'] == loc_val
                    
                    # PRESISI SN: Jika Excel dan WA sama-sama punya SN, Wajib Exact Match!
                    sn_match_ok = True
                    if sn_val and record['sn_norm']:
                        sn_match_ok = (sn_val == record['sn_norm'])
                    
                    if bin_match_ok and loc_match_ok and sn_match_ok:
                        matched_evidences.append(record['evidence'])
                        
            if matched_evidences:
                return " || ".join(list(dict.fromkeys(matched_evidences)))
            return "-"

        df_open['Asal_Sheet'] = sheet
        df_open['Pembelaan WhatsApp Lapangan'] = df_open.apply(find_matching_wa, axis=1)
        
        df_matched = df_open[df_open['Pembelaan WhatsApp Lapangan'] != "-"].copy()
        
        if 'Result' in df_matched.columns:
            df_matched['Jenis Finding'] = df_matched['Result']
        elif 'Remark' in df_matched.columns:
            df_matched['Jenis Finding'] = df_matched['Remark']
        elif 'Diff' in df_matched.columns:
            df_matched['Jenis Finding'] = df_matched['Diff'].apply(
                lambda x: 'MINUS' if x < 0 else ('SURPLUS' if x > 0 else 'MATCH')
            )
            
        if 'SN' in df_matched.columns:
            df_matched['SN'] = df_matched['SN'].fillna('-').astype(str).str.strip()
            
        if not df_matched.empty:
            target_cols = ['Asal_Sheet', 'LOC', 'BIN', 'PN', 'SN', 'Qty eMRO', 'Qty Actual', 'Diff', 'Jenis Finding', 'Status', 'Pembelaan WhatsApp Lapangan']
            valid_cols = [c for c in target_cols if c in df_matched.columns]
            all_reconciled_dfs.append(df_matched[valid_cols])
        
    df_final = pd.concat(all_reconciled_dfs, ignore_index=True) if all_reconciled_dfs else pd.DataFrame()
    return total_chat_in_range, df_final


if wa_file is not None and excel_file is not None:
    with st.spinner("Sedang memproses & menyaring bukti pembelaan auditee... Mohon tunggu..."):
        total_chats, df_final_open = process_whatsapp_and_excel(
            wa_file.getvalue(), 
            excel_file.getvalue(), 
            start_dt, 
            end_dt
        )
        
    st.info(f"🔹 Hasil Scan WhatsApp: Ditemukan {total_chats} balon chat di dalam rentang tanggal pilihan.")
    
    if not df_final_open.empty:
        st.success(f"🎯 Sukses Rekonsiliasi! Berhasil merangkum {len(df_final_open)} baris temuan OPEN yang memiliki pembelaan MURNI dari Auditee.")
        
        st.markdown("### 📊 Preview Hasil Rekonsiliasi Murni Auditee")
        st.dataframe(df_final_open, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_final_open.to_excel(writer, index=False, sheet_name='Hasil_Murni_Auditee')
            
        st.markdown("### 📥 Download Hasil Rekap Murni")
        st.download_button(
            label="📊 Download Excel Rekonsiliasi Murni Auditee (.xlsx)",
            data=buffer.getvalue(),
            file_name="hasil_rekonsiliasi_auditee_pure.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning("⚠️ Tidak ada kecocokan data 'OPEN' dari Worksheet Utama yang memiliki pembelaan/solusi valid dari Auditee di WhatsApp.")
else:
    st.info("👋 Silakan upload file Excel Stock Opname dan file TXT Chat WhatsApp lo di atas untuk memulai.")
