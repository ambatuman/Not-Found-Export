import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(
    page_title="WhatsApp Automated Audit to Excel",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ WhatsApp Automated Audit Extractor (Universal Format)")
st.write("Aplikasi ini otomatis mendukung chat tipe **satuan (non-looping)** maupun **banyak barang sekaligus (looping)**.")

st.divider()

uploaded_file = st.file_uploader("Upload file chat WhatsApp (.txt) di sini:", type=["txt"])

if uploaded_file is not None:
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    chat_content = stringio.read()
    
    # Pecah per balon chat berdasarkan format timestamp WhatsApp
    message_blocks = re.split(r'(?=\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*)', chat_content)
    
    parsed_data = []
    
    for block in message_blocks:
        if not block.strip():
            continue
            
        # Filter hanya chat yang berisi pembelaan atas temuan "NOT FOUND"
        if "not found" in block.lower():
            # 1. Cari lokasi BIN (Mendukung format: BIN BAT-TL291, AT BAT-TL078, atau BIN-A01)
            bin_match = re.search(r'(?:BIN|AT|DI)\s*#?\s*([A-Za-z0-9\-]+)', block, re.IGNORECASE)
            bin_val = bin_match.group(1) if bin_match else "-"
            
            # Ambil prefiks lokasi gudang (Loc) jika ada tanda minus (-) di nama BIN
            loc_val = "-"
            if bin_val != "-" and "-" in bin_val:
                loc_val = bin_val.split("-")[0]
                
            lines = block.split("\n")
            has_items = False
            
            # 2. Scan per baris untuk mencari PN dan SN
            for line in lines:
                # Regex fleksibel: Bisa mendeteksi PN#, PN:, PN-, atau Part Number
                if any(x in line.upper() for x in ["PN", "PART NUMBER", "PART NO"]):
                    has_items = True
                    
                    # Ekstraksi kode PN (mengambil karakter alfanumerik setelah tanda pemisah)
                    pn_match = re.search(r'(?:PN|Part\s*Number|Part\s*No)[:#\-\s]*([A-Za-z0-9\-]+)', line, re.IGNORECASE)
                    pn_val = pn_match.group(1) if pn_match else "-"
                    
                    # Ekstraksi kode SN jika ada di baris tersebut
                    sn_match = re.search(r'(?:SN|Serial|S/N)[:#\-\s]*([A-Za-z0-9\-]+)', line, re.IGNORECASE)
                    sn_val = sn_match.group(1) if sn_match else "-"
                    
                    # Cari quantity spesifik di baris tersebut, jika tidak ada default ke 1
                    qty_match = re.search(r'(\d+)\s*(?:pcs|qty|item|buah)', line, re.IGNORECASE)
                    qty_val = int(qty_match.group(1)) if qty_match else 1
                    
                    parsed_data.append({
                        "Loc": loc_val,
                        "BIN": bin_val,
                        "PN": pn_val,
                        "SN": sn_val,
                        "Quantity": qty_val,
                        "Remark": "Found at BIN"
                    })
            
            # 3. ANTISIPASI NON-LOOPING POLOS
            # Jika chat mengandung 'NOT FOUND' & info 'BIN' tapi auditee nulisnya polos tanpa sebut kata 'PN' atau 'SN'
            if not has_items:
                parsed_data.append({
                    "Loc": loc_val,
                    "BIN": bin_val,
                    "PN": "-",
                    "SN": "-",
                    "Quantity": 1,
                    "Remark": f"Review Manual: {block.strip()[:100]}..."
                })

    if parsed_data:
        df = pd.DataFrame(parsed_data)
        
        st.success(f"🎉 Mantap! Berhasil memproses data chat. Total terdeteksi: {len(df)} baris data.")
        st.dataframe(df, use_container_width=True)
        
        # Buat Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Audit_Findings_Found')
            
        st.markdown("### 📥 Download File Excel Lu")
        st.download_button(
            label="📊 Download File Excel Langsung (.xlsx)",
            data=buffer.getvalue(),
            file_name="rekap_pembelaan_universal.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning("⚠️ File berhasil dibaca, tapi tidak ada pola data audit yang cocok.")
