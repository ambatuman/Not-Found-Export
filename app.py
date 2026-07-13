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
st.write("Versi Super Akurat: Menghapus total tebakan jarak pesan. Pembelaan hanya diambil jika ada bukti penyelesaian valid di balon chat yang sama.")

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
                st.success(f"🎯 Terdeteksi {len(df_open)} baris temuan berstatus OPEN di Excel. Memproses data secara riil...")
                
                pembelaan_list = []
                
                for idx, row in df_open.iterrows():
                    pn_target = str(row['PN']).strip().lower()
                    no_finding_target = str(row['No']).strip() if 'No' in df_open.columns else ""
                    
                    found_evidence = "-"
                    
                    # Cari chat WA paling terbaru (terupdate) yang VALID membela barang ini
                    for wa in reversed(valid_wa_records):
                        chat_lower = wa['text_lower']
                        
                        # Cek kecocokan nomor finding atau nomor part number (PN)
                        has_finding_no_match = False
                        if no_finding_target:
                            no_patterns = [rf'\bno\s*{no_finding_target}\b', rf'\bfinding\s*no\s*{no_finding_target}\b', rf'\bno\.\s*{no_finding_target}\b']
                            if any(re.search(pat, chat_lower) for pat in no_patterns):
                                has_finding_no_match = True
                                
                        has_pn_match = (len(pn_target) > 3 and pn_target in chat_lower)
                        
                        if has_finding_no_match or has_pn_match:
                            # KAMUS VALIDASI: Harus ada kata penanda tindakan penyelesaian di balon chat tersebut
                            # Teks komplain murni tanpa kata ini otomatis diabaikan karena belum diselesaikan
                            keywords_valid_solusi = [
                                "found", "rts", "match", "issued", "transfer", "pindah", 
                                "done", "solved", "terpasang", "di rcm", "di cs", "bagus", "✅"
                            ]
                            
                            # Jika chat tersebut mengandung kata kelolosan solusi
                            if any(k in chat_lower for k in keywords_valid_solusi):
                                # Ekstrak baris REMARK jika format vertikal, atau ambil teks ringkas
                                lines = wa['clean_text'].split("\n")
                                extracted_remark = ""
                                for line in lines:
                                    if any(r in line.upper() for r in ["REMARK", "REMAKS"]) and ":" in line:
                                        extracted_remark = line.split(":", 1)[-1].strip()
                                        break
                                
                                if extracted_remark:
                                    found_evidence = f"[{wa['sender']}] -> {extracted_remark}"
                                else:
                                    main_text = wa['clean_text'].replace('\n', ' | ')
                                    found_evidence = f"[{wa['sender']}] -> {main_text}"
                                break # Keluar dari loop setelah menemukan pembelaan terupdate yang valid
                                
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
                    file_name="hasil_rekonsiliasi_pembelaan_so_open_perfect.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
    except Exception as e:
        st.error(f"❌ Terjadi kesalahan pembacaan Excel: {str(e)}")
