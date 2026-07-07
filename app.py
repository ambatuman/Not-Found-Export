import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(
    page_title="WhatsApp Automated Audit to Excel",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ WhatsApp Automated Audit Extractor (Fixed Multi-Format)")
st.write("Versi perbaikan mendeteksi format chat vertikal dengan urutan kata 'NOT FOUND' di bagian mana pun.")

st.divider()

uploaded_file = st.file_uploader("Upload file chat WhatsApp (.txt) di sini:", type=["txt"])

if uploaded_file is not None:
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    chat_content = stringio.read()
    
    # Pecah balon chat berdasarkan timestamp WhatsApp
    message_blocks = re.split(r'(?=\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*)', chat_content)
    
    parsed_data = []
    
    for block in message_blocks:
        if not block.strip():
            continue
            
        # Cek apakah balon chat mengandung kata 'NOT FOUND' (di posisi mana pun)
        if "not found" in block.lower():
            lines = block.split("\n")
            
            # Variabel penampung data per blok chat
            loc_val = "-"
            bin_val = "-"
            pn_val = "-"
            sn_val = "-"
            qty_val = 1
            remark_val = "Found"
            
            # Flag untuk mendeteksi apakah ini format vertikal/titik dua
            is_vertical_format = False
            
            # Koreksi 1: Ekstraksi presisi dengan basis pencarian baris vertikal (Mendeteksi tanda ':')
            for line in lines:
                line_clean = line.strip()
                if ":" in line_clean:
                    parts = line_clean.split(":", 1)
                    key = parts[0].strip().upper()
                    val = parts[1].strip()
                    
                    if "LOC" in key:
                        loc_val = val
                        is_vertical_format = True
                    elif "BIN" in key:
                        bin_val = val
                        is_vertical_format = True
                    elif "PN" in key:
                        # Mengambil seluruh isi setelah 'PN:' tanpa terpotong tanda miring (/)
                        pn_val = val
                        is_vertical_format = True
                    elif "SN" in key:
                        sn_val = val
                        is_vertical_format = True
                    elif "QTY EMRO" in key or "QTY" in key:
                        # Ambil angka saja dari QTY
                        qty_match = re.search(r'(\d+)', val)
                        if qty_match:
                            qty_val = int(qty_match.group(1))
            
            # Cari baris penyelesaian/remarks tambahan di luar struktur titik dua
            for line in lines:
                if "Penyelesaian" in line or "*" in line:
                    remark_val = line.replace("*", "").replace("Penyelesaian :", "").strip()
                    break

            # Jika formatnya vertikal, langsung masukkan data yang sudah dikumpulkan
            if is_vertical_format:
                parsed_data.append({
                    "Loc": loc_val,
                    "BIN": bin_val,
                    "PN": pn_val,
                    "SN": sn_val,
                    "Quantity": qty_val,
                    "Remark": remark_val if remark_val != "Found" else "Found at location"
                })
            else:
                # Koreksi 2: Jalankan pencarian horizontal/looping biasa jika format chat-nya tipe lama (PN# , SN#)
                has_items = False
                # Cari ulang info BIN & Loc global di chat tipe lama
                bin_match = re.search(r'(?:BIN|AT|DI)\s*#?\s*([A-Za-z0-9\-]+)', block, re.IGNORECASE)
                bin_global = bin_match.group(1) if bin_match else "-"
                loc_global = bin_global.split("-")[0] if "-" in bin_global else "-"
                
                for line in lines:
                    if any(x in line.upper() for x in ["PN", "PART NUMBER"]):
                        has_items = True
                        pn_match = re.search(r'(?:PN|Part\s*Number|Part\s*No)[:#\-\s]*([A-Za-z0-9\-]+)', line, re.IGNORECASE)
                        sn_match = re.search(r'(?:SN|Serial|S/N)[:#\-\s]*([A-Za-z0-9\-]+)', line, re.IGNORECASE)
                        
                        parsed_data.append({
                            "Loc": loc_global,
                            "BIN": bin_global,
                            "PN": pn_match.group(1) if pn_match else "-",
                            "SN": sn_match.group(1) if sn_match else "-",
                            "Quantity": 1,
                            "Remark": "Found at BIN (Format Borongan)"
                        })
                
                # Pengaman untuk chat pendek tanpa format PN/SN yang jelas
                if not has_items:
                    parsed_data.append({
                        "Loc": loc_global,
                        "BIN": bin_global,
                        "PN": "-",
                        "SN": "-",
                        "Quantity": 1,
                        "Remark": f"Review Manual: {block.strip()[:100]}..."
                    })

    if parsed_data:
        df = pd.DataFrame(parsed_data)
        
        st.success(f"🎉 Mantap! Berhasil memproses data chat. Total terdeteksi: {len(df)} baris data.")
        st.dataframe(df, use_container_width=True)
        
        # Simpan ke Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Audit_Findings_Found')
            
        st.markdown("### 📥 Download File Excel Lu")
        st.download_button(
            label="📊 Download File Excel Langsung (.xlsx)",
            data=buffer.getvalue(),
            file_name="rekap_pembelaan_fixed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning("⚠️ File berhasil dibaca, tetapi tidak ada pola data audit yang cocok.")
