import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(
    page_title="WhatsApp Multi-Location Audit Extractor",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ WhatsApp Automated Audit Extractor (Multi-Location Engine)")
st.write("Versi Akurasi Tinggi: Menarik semua data penemuan baik yang berstatus NOT FOUND awal maupun yang langsung dilaporkan FOUND oleh tim lapangan.")

st.divider()

uploaded_file = st.file_uploader("Upload file chat WhatsApp (.txt) lokasi mana saja di sini:", type=["txt"])

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
        lines = block.split("\n")
        
        # PERBAIKAN UTAMA: Saringan dilonggarkan agar status langsung "FOUND" murni ikut ketarik (Target 70+ Baris)
        if "not found" in block_lower or "missing" in block_lower or "found" in block_lower:
            
            # --- DETEKSI FORMAT VERTIKAL / SUB S1 STYLE ---
            is_vertical_format = any(":" in line.strip() and not line.strip().startswith(tuple(str(i) for i in range(10))) for line in lines)
            
            if is_vertical_format:
                loc_val, bin_val, pn_val, sn_val, qty_val, remark_val = "-", "-", "-", "-", 1, "-"
                additional_remark = ""
                has_pn_vertical = False
                
                # Cari nomor finding untuk style Surabaya jika tersedia
                finding_no = ""
                find_match = re.search(r'(?:Finding No|No Finding)\s*(\d+)', block, re.IGNORECASE)
                if find_match:
                    finding_no = f"Finding No.{find_match.group(1)} - "
                
                for line in lines:
                    line_clean = line.strip()
                    if ":" in line_clean and not line_clean.startswith(tuple(str(i) for i in range(10))):
                        parts = line_clean.split(":", 1)
                        key = parts[0].strip().upper()
                        val = parts[1].strip()
                        
                        if "LOC" in key: 
                            loc_val = val
                        elif "BIN EMRO" in key or "BIN ACTUAL" in key or "BIN ACT" in key: 
                            bin_val = val
                        elif "BIN" in key and bin_val == "-": 
                            bin_val = val
                        elif "P/N" in key or "PN" in key or "PART NUMBER" in key: 
                            pn_val = val
                            if val != "-" and val != "":
                                has_pn_vertical = True
                        elif "SN" in key: 
                            sn_val = val
                        elif "QTY ACT" in key or "QTY ACTUAL" in key or "QTY" in key:
                            qty_match = re.search(r'(\d+)', val)
                            if qty_match: qty_val = int(qty_match.group(1))
                        elif "REMARK" in key: 
                            remark_val = val

                # Cari kalimat aksi penemuan (Found at / RTS Done) untuk style Surabaya di sisa baris
                action_remark = ""
                for line in lines:
                    line_upper = line.upper()
                    if any(k in line_upper for k in ["FOUND AT", "TRANSFER BIN", "DONE", "RTS"]):
                        if ":" not in line:
                            action_remark = " " + line.strip()
                            break

                for line in lines:
                    if "PENYELESAIAN" in line.upper() or line.strip().startswith("*"):
                        additional_remark = " " + line.strip().replace("*", "")
                        break
                
                if remark_val == "-" or remark_val == "": 
                    remark_val = "Found/Resolved"
                
                # Gabungkan remark biar informatif lengkap
                remark_val = finding_no + remark_val + action_remark + additional_remark
                
                # Jika di format Surabaya lokasinya tidak tertulis eksplisit, auto-fill pakai 'SUB' berdasarkan nama BIN
                if loc_val == "-" and bin_val != "-":
                    if "SUB" in bin_val.upper() or "SUB" in block:
                        loc_val = "SUB"
                    elif bin_val.startswith("BAT"):
                        loc_val = "BAT"

                # Masukkan data jika lolos validasi PN
                if has_pn_vertical and pn_val != "-":
                    parsed_data.append({
                        "Loc": loc_val, "BIN": bin_val, "PN": pn_val, "SN": sn_val, "Quantity": qty_val, "Remark": remark_val
                    })
                
            else:
                # --- FORMAT HORIZONTAL / BORONGAN JAKARTA STYLE (PN# , SN#) ---
                clean_block = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*[^:]+:\s*', '', block, flags=re.IGNORECASE)
                clean_lines = clean_block.split("\n")
                
                bin_global = "-"
                remark_global = "Found"
                
                for line in clean_lines:
                    line_upper = line.upper()
                    if any(k in line_upper for k in ["BIN", "FOUND AT", "TRANSFER"]):
                        bin_match = re.search(r'\b([A-Za-z0-9]+-[A-Za-z0-9\-]+)\b', line)
                        if bin_match:
                            bin_global = bin_match.group(1).strip()
                            break
                
                if bin_global == "-":
                    for line in clean_lines:
                        bin_match = re.search(r'(?:BIN|AT|DI)\s*#?\s*([A-Za-z0-9\-]+)', line, re.IGNORECASE)
                        if bin_match and bin_match.group(1).upper() not in ["BIN", "AT", "DI", "FOUND"]:
                            bin_global = bin_match.group(1).strip()
                            break
                            
                loc_global = bin_global.split("-")[0] if "-" in bin_global else "-"
                
                for line in reversed(clean_lines):
                    if any(k in line.upper() for k in ["FOUND", "TRANSFER", "ISSUED", "REMARK"]):
                        remark_global = line.strip()
                        break
                
                for line in clean_lines:
                    if any(x in line.upper() for x in ["PN#", "PN ", "PART NUMBER"]):
                        pn_match = re.search(r'(?:PN#|PN|Part\s*Number)[:\s-]*([A-Za-z0-9\-/]+)', line, re.IGNORECASE)
                        sn_match = re.search(r'(?:SN#|SN|Serial|S/N)[:\s-]*([A-Za-z0-9\-]+)', line, re.IGNORECASE)
                        qty_match = re.search(r'(?:QTY#|QTY)[:\s-]*(\d+)|(\d+)\s*(?:pcs|qty|item)', line, re.IGNORECASE)
                        
                        if qty_match:
                            qty_val = int(qty_match.group(1)) if qty_match.group(1) else int(qty_match.group(2))
                        else:
                            qty_val = 1
                            
                        parsed_data.append({
                            "Loc": loc_global, "BIN": bin_global, "PN": pn_match.group(1).strip() if pn_match else "-", "SN": sn_match.group(1).strip() if sn_match else "-", "Quantity": qty_val, "Remark": remark_global
                        })

    if parsed_data:
        df_raw = pd.DataFrame(parsed_data)
        
        # Tameng filter surplus / minus harian murni tanpa status pencarian barang
        def filter_strict_pembelaan(row):
            rem = str(row['Remark']).upper()
            if any(trash in rem for trash in ["SURPLUS", "MINUS", "WRONG BINNING", "UNRECORDED"]):
                if any(save in rem for save in ["FOUND", "TRANSFER", "ISSUED", "MISSING", "NOT FOUND", "RESOLVED"]):
                    return True
                return False
            return True

        df_filtered = df_raw[df_raw.apply(filter_strict_pembelaan, axis=1)]
        
        # Rekonsiliasi data duplikat update chat (keep='last')
        df = df_filtered.drop_duplicates(subset=["BIN", "PN", "SN"], keep="last").reset_index(drop=True)
        
        st.success(f"🎉 Sukses Besar! Sistem Multi-Lokasi berhasil memproses data chat. Total data final valid: {len(df)} baris.")
        st.dataframe(df, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Audit_Findings_Found')
            
        st.markdown("### 📥 Download File Excel Gabungan")
        st.download_button(
            label="📊 Download File Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="rekap_pembelaan_multi_lokasi_fixed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
