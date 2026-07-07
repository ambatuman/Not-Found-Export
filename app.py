import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(
    page_title="WhatsApp Automated Audit to Excel",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ WhatsApp Automated Audit Extractor (Zero Input)")
st.write("Upload file `.txt` chat WhatsApp lu, sistem bakal otomatis nge-parsing semua temuan **'not found'** jadi tabel Excel tanpa lu perlu ngetik apa-apa lagi.")

st.divider()

# Tempat upload file .txt
uploaded_file = st.file_uploader("Upload file chat WhatsApp (.txt) di sini:", type=["txt"])

if uploaded_file is not None:
    # Membaca isi file text
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    chat_lines = stringio.readlines()
    
    parsed_data = []
    
    # Looping otomatis untuk menyaring data chat
    for line in chat_lines:
        if "not found" in line.lower():
            clean_line = line.strip()
            
            # 1. Bersihkan format timestamp & nama pengirim dari WhatsApp
            message_content = clean_line
            if " - " in clean_line and ":" in clean_line:
                parts = clean_line.split(":", 1)
                if len(parts) > 1 and " - " in parts[0]:
                    message_content = parts[1].strip()
            elif "]" in clean_line and ":" in clean_line:
                parts = clean_line.split(":", 2)
                message_content = parts[-1].strip()
                
            # 2. EKSTRAKSI OTOMATIS MENGGUNAKAN LOGIKA TEKS (REGEX)
            
            # Cari lokasi BIN / Lokasi setelah kata "AT" atau "DI" (Contoh: BAT-TL088-AVL10)
            bin_match = re.search(r'(?:not found at|not found di)\s+([A-Za-z0-9\-]+)', message_content, re.IGNORECASE)
            bin_val = bin_match.group(1) if bin_match else "-"
            
            # Ambil singkatan lokasi depan dari nama BIN jika ada (Contoh: BAT dari BAT-TL088)
            loc_val = "-"
            if bin_val != "-" and "-" in bin_val:
                loc_val = bin_val.split("-")[0]
            
            # Cari remark/keterangan tambahan di dalam tanda kurung (Contoh: MISSING AT EMRO)
            remark_match = re.search(r'\((.*?)\)', message_content)
            remark_val = remark_match.group(1) if remark_match else "-"
            
            # Jika polanya polos tanpa kurung, teks aslinya kita jadikan remark
            if bin_val == "-" and remark_val == "-":
                remark_val = message_content
                
            # Deteksi otomatis Part Number (PN) jika tertulis di chat
            pn_match = re.search(r'(?:PN|Part Number)[:\s-]*([A-Za-z0-9\-]+)', message_content, re.IGNORECASE)
            pn_val = pn_match.group(1) if pn_match else "-"
            
            # Deteksi otomatis Serial Number (SN) jika tertulis di chat
            sn_match = re.search(r'(?:SN|Serial|S/N)[:\s-]*([A-Za-z0-9\-]+)', message_content, re.IGNORECASE)
            sn_val = sn_match.group(1) if sn_match else "-"
            
            # Deteksi quantity jika terdeteksi format angka (default 1 kalau tidak tertulis spesifik)
            qty_match = re.search(r'(\d+)\s*(?:pcs|qty|item|buah)', message_content, re.IGNORECASE)
            qty_val = int(qty_match.group(1)) if qty_match else 1
            
            # Gabungkan semua ke bentuk baris Excel
            parsed_data.append({
                "Loc": loc_val,
                "BIN": bin_val,
                "PN": pn_val,
                "SN": sn_val,
                "Quantity": qty_val,
                "Remark": f"Auto-extracted: {message_content}" if remark_val == "-" else remark_val
            })
            
    if parsed_data:
        df = pd.DataFrame(parsed_data)
        
        st.success(f"🎉 Mantap! Otomatis mendeteksi dan mengekstrak {len(df)} baris data 'Not Found'.")
        
        # Tampilkan Preview Tabel Lengkap biar lu bisa ngecek hasilnya langsung di web
        st.markdown("### 📋 Preview Data Hasil Parsing Otomatis")
        st.dataframe(df, use_container_width=True)
        
        # Proses konversi data langsung ke Excel (.xlsx) di dalam background
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Automated_Findings')
            
        # Tombol Download Excel Langsung muncul tanpa interaksi tambahan
        st.markdown("### 📥 Download File Excel Lu")
        st.download_button(
            label="📊 Download File Excel Langsung (.xlsx)",
            data=buffer.getvalue(),
            file_name="hasil_otomatis_chat_audit.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning("⚠️ File `.txt` berhasil dibaca, tapi gak ada chat yang mengandung kata kunci 'not found'.")
        
