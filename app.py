import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime

st.set_page_config(
    page_title="WhatsApp Audit Reconciler - Two-File Engine v3",
    page_icon="📊",
    layout="wide"
)

st.title("📊 WhatsApp Audit Reconciler (Two-File Precision Engine - V3 Perfect)")
st.write("Versi Pemungkas: Menggabungkan balon chat terpisah (rincian finding + konfirmasi lapangan) secara cerdas.")

st.divider()

# --- PILIHAN FILTER TANGGAL ---
st.sidebar.header("📅 Pengaturan Filter Tanggal Chat")
start_date = st.sidebar.date_input("Tanggal Awal Chat:", value=datetime(2026, 6, 8))
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
    message_blocks = re.split(r'(?=\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*)', wa_string)
    
    valid_wa_records = []
    
    for block in message_blocks:
        if not block.strip():
            continue
            
        time_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2})', block.strip())
        if time_match:
            date_str = time_match.group(1)
            try:
                msg_date = datetime.strptime(date_str, "%m/%d/%y")
            except ValueError:
                try:
                    msg_date = datetime.strptime(date_str, "%m/%d/%Y")
                except ValueError:
                    msg_date = None
            
            if msg_date and (start_dt <= msg_date <= end_dt):
                clean_text = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*[^:]+:\s*', '', block, flags=re.IGNORECASE).strip()
                
                # Ekstrak nama pengirim chat
                meta_match = re.match(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*([^:]+):', block.strip())
                sender = meta_match.group(1).strip() if meta_match else "Store Lapangan"
                
                valid_wa_records.append({
                    "sender": sender,
                    "clean_text": clean_text,
                    "text_lower": clean_text.lower()
                })
                
    st.info(f"🔹 Hasil Scan WhatsApp: Ditemukan {len(valid_wa_records)} baris chat di dalam rentang tanggal pilihan.")

    # 2. BACA DATA MASTER EXCEL AUDIT
    try:
        xls = pd.ExcelFile(excel_file)
        sheet_target = 'Worksheet' if 'Worksheet' in xls.sheet_names else xls.sheet_names[0]
        df_master = pd.read_excel(excel_file, sheet_name=sheet_target)
        
        if 'Status' not in df_master.columns or 'PN' not in df_master.columns:
            st.error("❌ Eror: Excel wajib memiliki kolom bernama 'Status' dan 'PN'.")
        else:
            df_open = df_master[df_master['Status'].astype(str).str.upper() == 'OPEN'].copy()
            
            if df_open.empty:
                st.warning("⚠️ Tidak ada data berstatus 'OPEN' yang perlu dicari pembelaannya.")
            else:
                st.success(f"🎯 Terdeteksi {len(df_open)} baris temuan berstatus OPEN di Excel. Memulai sinkronisasi cerdas...")
                
                pembelaan_list = []
                
                # LOOPING UTAMA DATA OPEN EXCEL
                for idx, row in df_open.iterrows():
                    pn_target = str(row['PN']).strip().lower()
                    no_finding_target = str(row['No']).strip() if 'No' in df_open.columns else ""
                    
                    found_evidence = "-"
                    
                    # Cari index chat yang cocok
                    for i, wa in enumerate(valid_wa_records):
                        chat_lower = wa['text_lower']
                        
                        # Cek kecocokan Finding Number atau Part Number
                        has_finding_no_match = False
                        if no_finding_target:
                            no_patterns = [rf'\bno\s*{no_finding_target}\b', rf'\bfinding\s*no\s*{no_finding_target}\b', rf'\bno\.\s*{no_finding_target}\b']
                            if any(re.search(pat, chat_lower) for pat in no_patterns):
                                has_finding_no_match = True
                                
                        has_pn_match = (len(pn_target) > 3 and pn_target in chat_lower)
                        
                        if has_finding_no_match or has_pn_match:
                            # Teks utama dari balon chat berisi info PN
                            main_text = wa['clean_text'].replace('\n', ' | ')
                            found_evidence = f"[{wa['sender']}] -> {main_text}"
                            
                            # LOGIKA SMART CONTEXT LOOK-AHEAD: Intip hingga 3 pesan setelahnya untuk mencari konfirmasi sukses
                            follow_up_texts = []
                            for j in range(i + 1, min(i + 4, len(valid_wa_records))):
                                next_wa = valid_wa_records[j]
                                next_text_lower = next_wa['text_lower']
                                
                                # Jika pesan selanjutnya super pendek dan mengandung kata konfirmasi/solusi
                                if any(k in next_text_lower for k in ["done", "issued", "rts", "match", "found", "solved"]):
                                    # Cegah ketariknya finding baru orang lain yang tidak sengaja berurutan
                                    if "pn :" not in next_text_lower and "loc :" not in next_text_lower:
                                        follow_up_texts.append(f"[{next_wa['sender']}: {next_wa['clean_text']}]")
                            
                            if follow_up_texts:
                                found_evidence += " | FOLLOW-UP: " + " -> ".join(follow_up_texts)
                            
                            # Update dengan temuan paling baru jika ada duplikasi chat di bawah
                            continue 
                                
                    pembelaan_list.append(found_evidence)
                
                df_open['Pembelaan WhatsApp Lapangan'] = pembelaan_list
                
                st.markdown("### 📊 Preview Hasil Sinkronisasi Data OPEN vs WhatsApp")
                st.dataframe(df_open[['No', 'BIN', 'PN', 'Qty eMRO', 'Qty Actual', 'Status', 'Pembelaan WhatsApp Lapangan']], use_container_width=True)
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_open.to_excel(writer, index=False, sheet_name='Hasil_Rekonsiliasi_Open')
                    
                st.markdown("### 📥 Download Hasil Rekap Data Open Terupdate")
                st.download_button(
                    label="📊 Download Excel Pembelaan Ter-Reconcile (.xlsx)",
                    data=buffer.getvalue(),
                    file_name="hasil_rekonsiliasi_pembelaan_so_open.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
    except Exception as e:
        st.error(f"❌ Terjadi kesalahan pembacaan Excel: {str(e)}")
