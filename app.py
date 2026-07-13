import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime

st.set_page_config(
    page_title="WhatsApp Audit Reconciler - Two-File Engine",
    page_icon="📊",
    layout="wide"
)

st.title("📊 WhatsApp Audit Reconciler (Two-File Precision Engine)")
st.write("Sistem Pencocokan Otomatis: Mencari pembelaan chat WhatsApp berdasarkan daftar finding Excel yang masih berstatus **OPEN**.")

st.divider()

# --- PILIHAN FILTER TANGGAL (ANTI TERCAMPUR BULAN LALU) ---
st.sidebar.header("📅 Pengaturan Filter Tanggal Chat")
st.sidebar.write("Batasi rentang waktu chat WhatsApp agar obrolan bulan lalu tidak tidak dianggap sebagai penyelesaian audit sekarang.")

start_date = st.sidebar.date_input("Tanggal Awal Chat:", value=datetime(2026, 5, 1))
end_date = st.sidebar.date_input("Tanggal Akhir Chat:", value=datetime(2026, 7, 31))

# Konversi filter tanggal ke objek datetime untuk komparasi logika
start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())

# --- INTERFACE UPLOAD DUA FILE ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 1️⃣ File Txt WhatsApp")
    wa_file = st.file_uploader("Upload file chat WhatsApp (.txt):", type=["txt"])

with col2:
    st.markdown("### 2️⃣ File Excel Audit Master")
    excel_file = st.file_uploader("Upload Master Excel Stock Take (.xlsx):", type=["xlsx"])

if wa_file is not None and excel_file is not None:
    # 1. BACA & PARSING WHATSAPP CHAT BERDASARKAN FILTER TANGGAL
    wa_string = io.StringIO(wa_file.getvalue().decode("utf-8")).read()
    
    # Pecah chat berdasarkan timestamp reguler WhatsApp
    message_blocks = re.split(r'(?=\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*)', wa_string)
    
    valid_wa_records = []
    
    for block in message_blocks:
        if not block.strip():
            continue
            
        # Ambil timestamp di awal baris chat
        time_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2})', block.strip())
        if time_match:
            date_str = time_match.group(1)
            # Coba konversi dengan format tahun 2 digit atau 4 digit
            try:
                msg_date = datetime.strptime(date_str, "%m/%d/%y")
            except ValueError:
                try:
                    msg_date = datetime.strptime(date_str, "%m/%d/%Y")
                except ValueError:
                    msg_date = None
            
            # Validasi Kelolosan Filter Tanggal
            if msg_date and (start_dt <= msg_date <= end_dt):
                # Bersihkan metadata agar menyisakan isi teks chat bersih
                clean_text = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*[^:]+:\s*', '', block, flags=re.IGNORECASE).strip()
                valid_wa_records.append({
                    "raw_block": block,
                    "clean_text": clean_text,
                    "text_lower": clean_text.lower()
                })
                
    st.info(f"🔹 Hasil Scan WhatsApp: Ditemukan {len(valid_wa_records)} baris chat di dalam rentang tanggal pilihan.")

    # 2. BACA DATA MASTER EXCEL AUDIT
    try:
        xls = pd.ExcelFile(excel_file)
        # Prioritas mencari sheet bernama 'Worksheet' atau fallback sheet pertama
        sheet_target = 'Worksheet' if 'Worksheet' in xls.sheet_names else xls.sheet_names[0]
        df_master = pd.read_excel(excel_file, sheet_name=sheet_target)
        
        # Cek kolom wajib status open
        if 'Status' not in df_master.columns or 'PN' not in df_master.columns:
            st.error("❌ Eror: Excel wajib memiliki kolom bernama 'Status' dan 'PN'. Silakan periksa file Excel lu.")
        else:
            # Ambil data baris yang murni berstatus OPEN saja
            df_open = df_master[df_master['Status'].astype(str).str.upper() == 'OPEN'].copy()
            
            if df_open.empty:
                st.warning("⚠️ Semua data di Excel berstatus MATCHED/CLOSED. Tidak ada data berstatus 'OPEN' yang perlu dicari pembelaannya.")
            else:
                st.success(f"🎯 Terdeteksi {len(df_open)} baris temuan berstatus OPEN di Excel. Memulai proses tracking ke WhatsApp...")
                
                pembelaan_list = []
                timestamp_list = []
                
                # LOOPING PRESISI: Cari pembelaan di WA chat untuk setiap baris barang OPEN
                for idx, row in df_open.iterrows():
                    pn_target = str(row['PN']).strip().lower()
                    no_finding_target = str(row['No']).strip() if 'No' in df_open.columns else ""
                    
                    found_evidence = "-"
                    evidence_time = "-"
                    
                    # Cari chat WA paling terakhir (terupdate) yang membela barang ini
                    for wa in reversed(valid_wa_records):
                        chat_lower = wa['text_lower']
                        
                        # Indikator 1: Deteksi via kecocokan nomor Finding No (Contoh: No 655 atau Finding No 655)
                        has_finding_no_match = False
                        if no_finding_target:
                            no_patterns = [
                                rf'\bno\s*{no_finding_target}\b',
                                rf'\bfinding\s*no\s*{no_finding_target}\b',
                                rf'\bno\.\s*{no_finding_target}\b'
                            ]
                            if any(re.search(pat, chat_lower) for pat in no_patterns):
                                has_finding_no_match = True
                                
                        # Indikator 2: Deteksi langsung lewat nomor part number (PN) unik
                        has_pn_match = (len(pn_target) > 3 and pn_target in chat_lower)
                        
                        if has_finding_no_match or has_pn_match:
                            # Validasi apakah isi chatnya bernada solusi nyata (bukan sekadar komplain ulang)
                            keywords_solusi = ["found", "rts", "match", "issued", "transfer", "ada", "sewaktu so", "di rcm", "di cs", "pesawat"]
                            if any(k in chat_lower for k in keywords_solusi):
                                # Ekstrak pengirim dan jam waktu
                                meta_match = re.match(r'^([^\n]+-\s*[^:]+):', wa['raw_block'].strip())
                                meta_info = meta_match.group(1) if meta_match else "WhatsApp Evidence"
                                
                                found_evidence = f"[{meta_info}] -> {wa['clean_text']}"
                                break
                                
                    pembelaan_list.append(found_evidence)
                
                # Masukkan hasil pelacakan WhatsApp ke kolom baru Excel
                df_open['Pembelaan WhatsApp Lapangan'] = pembelaan_list
                
                # Tampilkan tabel preview hasil rekonsiliasi data
                st.markdown("### 📊 Preview Hasil Sinkronisasi Data OPEN vs WhatsApp")
                st.dataframe(df_open[['No', 'BIN', 'PN', 'Qty eMRO', 'Qty Actual', 'Status', 'Pembelaan WhatsApp Lapangan']], use_container_width=True)
                
                # EXPORT KE EXCEL TERBARU
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
