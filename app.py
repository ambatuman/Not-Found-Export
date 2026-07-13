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
st.write("Versi Multi-Sheet & Auto-Extract: Pembelaan diambil jika ada bukti penyelesaian valid di balon chat yang sama.")

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

if wa_file is not None and excel_file is not None:
    # 1. BACA & PARSING WHATSAPP CHAT
    wa_string = io.StringIO(wa_file.getvalue().decode("utf-8")).read()
    # Regex split untuk memisahkan setiap balon chat WhatsApp
    message_blocks = re.split(r'(?=\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*)', wa_string)
    
    valid_wa_records = []
    
    for block in message_blocks:
        if not block.strip():
            continue
            
        time_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2})', block.strip())
        if time_match:
            date_str = time_match.group(1)
            # Coba beberapa variasi format penulisan tanggal chat WA
            for fmt in ("%m/%d/%y", "%m/%d/%Y", "%d/%m/%y", "%d/%m/%Y"):
                try:
                    msg_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    msg_date = None
            
            if msg_date and (start_dt <= msg_date <= end_dt):
                # Bersihkan metadata nama sender untuk mengambil text murni
                clean_text = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*[^:]+:\s*', '', block, flags=re.IGNORECASE).strip()
                
                meta_match = re.match(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*([^:]+):', block.strip())
                sender = meta_match.group(1).strip() if meta_match else "Store Lapangan"
                
                valid_wa_records.append({
                    "sender": sender,
                    "clean_text": clean_text,
                    "text_lower": clean_text.lower()
                })
                
    st.info(f"🔹 Hasil Scan WhatsApp: Ditemukan {len(valid_wa_records)} balon chat di dalam rentang tanggal pilihan.")

    # 2. BACA DATA MASTER EXCEL AUDIT (MULTI-SHEET SUPPORT)
    try:
        xls = pd.ExcelFile(excel_file)
        # Cari semua sheet yang mengandung kata 'DATA'
        data_sheets = [sheet for sheet in xls.sheet_names if 'DATA' in sheet.upper()]
        
        if not data_sheets:
            # Fallback ke sheet pertama jika tidak ada nama sheet yang mengandung kata 'DATA'
            data_sheets = [xls.sheet_names[0]]
            
        all_reconciled_dfs = []
        
        for sheet in data_sheets:
            df_master = pd.read_excel(xls, sheet_name=sheet)
            df_master.columns = df_master.columns.str.strip()
            
            # Cek ketersediaan kolom wajib minimal
            if 'Status' not in df_master.columns or 'PN' not in df_master.columns:
                st.warning(f"⚠️ Sheet '{sheet}' diabaikan karena tidak memiliki kolom 'Status' atau 'PN'.")
                continue
                
            # Filter baris yang berstatus OPEN (case-insensitive)
            df_open = df_master[df_master['Status'].astype(str).str.strip().str.upper() == 'OPEN'].copy()
            
            if df_open.empty:
                continue
                
            pembelaan_list = []
            
            for idx, row in df_open.iterrows():
                pn_target = str(row['PN']).strip().lower()
                no_finding_target = str(row['No']).strip() if 'No' in df_open.columns else ""
                
                found_evidence = "-"
                
                # Scan balik dari chat paling baru ke lama (reversed)
                for wa in reversed(valid_wa_records):
                    chat_lower = wa['text_lower']
                    
                    # Cek kecocokan Nomor Finding atau Part Number
                    has_finding_no_match = False
                    if no_finding_target and no_finding_target != "nan":
                        no_patterns = [rf'\bno\s*{no_finding_target}\b', rf'\bfinding\s*no\s*{no_finding_target}\b']
                        if any(re.search(pat, chat_lower) for pat in no_patterns):
                            has_finding_no_match = True
                            
                    has_pn_match = (len(pn_target) > 3 and pn_target in chat_lower)
                    
                    if has_finding_no_match or has_pn_match:
                        # Kamus Validasi Solusi Lapangan
                        keywords_valid_solusi = [
                            "found", "rts", "match", "issued", "transfer", "pindah", 
                            "done", "solved", "terpasang", "di rcm", "di cs", "bagus", "✅",
                            "penyele", "penyelesaian"
                        ]
                        
                        if any(k in chat_lower for k in keywords_valid_solusi):
                            lines = wa['clean_text'].split("\n")
                            extracted_remark = ""
                            
                            # Ekstrak teks spesifik setelah baris PENYELESAIAN / REMARK
                            for line in lines:
                                if any(r in line.upper() for r in ["PENYELESAIAN", "REMARK", "REMAKS"]) and ":" in line:
                                    extracted_remark = line.split(":", 1)[-1].strip()
                                    break
                            
                            if extracted_remark:
                                found_evidence = f"[{wa['sender']}] -> {extracted_remark}"
                            else:
                                main_text = wa['clean_text'].replace('\n', ' | ')
                                found_evidence = f"[{wa['sender']}] -> {main_text}"
                            break 
                            
                pembelaan_list.append(found_evidence)
            
            df_open['Asal_Sheet'] = sheet
            df_open['Pembelaan WhatsApp Lapangan'] = pembelaan_list
            all_reconciled_dfs.append(df_open)
            
        if all_reconciled_dfs:
            # Gabungkan hasil rekonsiliasi dari semua sheet data
            df_final_open = pd.concat(all_reconciled_dfs, ignore_index=True)
            
            st.success(f"🎯 Berhasil memproses total {len(df_final_open)} baris temuan berstatus OPEN dari seluruh sheet data!")
            
            st.markdown("### 📊 Preview Hasil Sinkronisasi Data OPEN vs WhatsApp")
            
            # Saring kolom yang tersedia secara fleksibel untuk preview tabel
            preview_cols = ['Asal_Sheet', 'PN', 'BIN', 'Status', 'Pembelaan WhatsApp Lapangan']
            if 'No' in df_final_open.columns: preview_cols.insert(1, 'No')
            if 'Qty eMRO' in df_final_open.columns: preview_cols.append('Qty eMRO')
            if 'Qty Actual' in df_final_open.columns: preview_cols.append('Qty Actual')
            
            st.dataframe(df_final_open[preview_cols], use_container_width=True)
            
            # Bungkus file output ke excel siap download
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
            st.warning("⚠️ Tidak ada data berstatus 'OPEN' yang ditemukan di seluruh sheet data.")
            
    except Exception as e:
        st.error(f"❌ Terjadi kesalahan pembacaan Excel: {str(e)}")
