import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(
    page_title="WhatsApp Automated Audit to Excel",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ WhatsApp Automated Audit Extractor (Anti-Metadata Bug)")
st.write("Versi 100% Aman: Menghapus total nomor HP pengirim dari teks sebelum proses ekstraksi data dimulai.")

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
            
        block_lower = block.lower()
        
        # Filter ketat status temuan awal (harus ada indikasi not found atau missing)
        if "not found" in block_lower or "missing" in block_lower:
            
            # === SOLUSI UTAMA: BERSIHKAN METADATA WHATSAPP ===
            # Kita bersihkan baris timestamp dan nomor HP/nama pengirim di awal blok chat
            # Contoh membersihkan: "6/26/26, 10:43 - +62 822-7927-3261: " atau "[06/26/26] Nama: "
            clean_block = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*[^:]+:\s*', '', block, flags=re.IGNORECASE)
            clean_block = re.sub(r'^\[\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}:\d{2}\]\s*[^:]+:\s*', '', clean_block, flags=re.IGNORECASE)
            
            lines = clean_block.split("\n")
            
            # Cek apakah ini format vertikal rapi (pakai titik dua ':')
            is_vertical_format = any(":" in line.strip() and not line.strip().startswith(tuple(str(i) for i in range(10))) for line in lines)
            
            if is_vertical_format:
                loc_val, bin_val, pn_val, sn_val, qty_val, remark_val = "-", "-", "-", "-", 1, "-"
                
                for line in lines:
                    line_clean = line.strip()
                    if ":" in line_clean:
                        parts = line_clean.split(":", 1)
                        key = parts[0].strip().upper()
                        val = parts[1].strip()
                        
                        if "LOC" in key: loc_val = val
                        elif "BIN" in key or "BIN ACTUAL" in key: bin_val = val
                        elif "PN" in key: pn_val = val
                        elif "SN" in key: sn_val = val
                        elif "QTY ACT" in key or "QTY" in key:
                            qty_match = re.search(r'(\d+)', val)
                            if qty_match: qty_val = int(qty_match.group(1))
                        elif "REMARK" in key: remark_val = val

                additional_remark = ""
                for line in lines:
                    if "PENYELESAIAN" in line.upper() or line.strip().startswith("*"):
                        additional_remark = " " + line.strip()
                        break
                
                if remark_val == "-" or remark_val == "": remark_val = "Found"
                remark_val = remark_val + additional_remark

                parsed_data.append({
                    "Loc": loc_val, "BIN": bin_val, "PN": pn_val, "SN": sn_val, "Quantity": qty_val, "Remark": remark_val
                })
                
            else:
                # FORMAT HORIZONTAL / BORONGAN (PN# , SN#)
                bin_global = "-"
                remark_global = "Found"
                
                # Cari baris yang mengandung kode BIN yang valid (pola alfanumerik dipisah strip, misal BAT-TL292)
                # Karena metadata nomor HP di baris teratas udah dibuang total di atas, pencarian ini dijamin aman!
                for line in lines:
                    line_upper = line.upper()
                    if "BIN" in line_upper or "FOUND AT" in line_upper or "LOC" in line_upper:
                        bin_match = re.search(r'\b([A-Za-z0-9]+-[A-Za-z0-9\-]+)\b', line)
                        if bin_match:
                            bin_global = bin_match.group(1).strip()
                            remark_global = line.strip()
                            break
                
                if bin_global == "-":
                    for line in lines:
                        bin_match = re.search(r'(?:BIN|AT|DI)\s*#?\s*([A-Za-z0-9\-]+)', line, re.IGNORECASE)
                        if bin_match and bin_match.group(1).upper() not in ["BIN", "AT", "DI", "FOUND"]:
                            bin_global = bin_match.group(1).strip()
                            remark_global = line.strip()
                            break
                
                loc_global = bin_global.split("-")[0] if "-" in bin_global else "-"
                
                has_items = False
                for line in lines:
                    if any(x in line.upper() for x in ["PN#", "PN ", "PART NUMBER"]):
                        has_items = True
                        pn_match = re.search(r'(?:PN#|PN|Part\s*Number)[:\s-]*([A-Za-z0-9\-/]+)', line, re.IGNORECASE)
                        sn_match = re.search(r'(?:SN#|SN|Serial|S/N)[:\s-]*([A-Za-z0-9\-]+)', line, re.IGNORECASE)
                        qty_match = re.search(r'(?:QTY#|QTY)[:\s-]*(\d+)|(\d+)\s*(?:pcs|qty|item)', line, re.IGNORECASE)
                        
                        if qty_match:
                            qty_val = int(qty_match.group(1)) if qty_match.group(1) else int(qty_match.group(2))
                        else:
                            qty_val = 1
                            
                        parsed_data.append({
                            "Loc": loc_global, 
                            "BIN": bin_global, 
                            "PN": pn_match.group(1).strip() if pn_match else "-", 
                            "SN": sn_match.group(1).strip() if sn_match else "-", 
                            "Quantity": qty_val, 
                            "Remark": remark_global
                        })
                        
                if not has_items:
                    parsed_data.append({
                        "Loc": loc_global, "BIN": bin_global, "PN": "-", "SN": "-", "Quantity": 1, "Remark": clean_block.strip()[:150]
                    })

    if parsed_data:
        df_raw = pd.DataFrame(parsed_data)
        # Saring duplikat berdasarkan baris terakhir (keep last untuk update chat penyelesaian)
        df = df_raw.drop_duplicates(subset=["BIN", "PN", "SN"], keep="last").reset_index(drop=True)
        
        st.success(f"🎉 Sukses! Berhasil memproses data chat. Bebas nomor HP & duplikasi. Total: {len(df)} baris.")
        st.dataframe(df, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Audit_Findings_Found')
            
        st.markdown("### 📥 Download File Excel Lu")
        st.download_button(
            label="📊 Download File Excel Langsung (.xlsx)",
            data=buffer.getvalue(),
            file_name="rekap_pembelaan_clean_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
