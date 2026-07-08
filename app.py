import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(
    page_title="WhatsApp Audit Extractor - Universal Ultimate Engine",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ WhatsApp Automated Audit Extractor (Universal Ultimate Engine)")
st.write("Versi Super Lem: Mempertahankan 100% logika teks universal lama + Jaring Otomatis untuk stasiun yang hanya kirim foto kosongan.")

st.divider()

uploaded_file = st.file_uploader("Upload file chat WhatsApp (.txt) di sini:", type=["txt"])

if uploaded_file is not None:
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    chat_content = stringio.read()
    
    # Pecah per balon chat berdasarkan format timestamp WhatsApp
    message_blocks = re.split(r'(?=\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*)', chat_content)
    
    parsed_data = []
    
    # List bantuan untuk menampung riwayat komplain (Not Found / Missing) demi fitur backtrack foto
    complaint_history = []
    
    for block in message_blocks:
        if not block.strip():
            continue
            
        block_lower = block.lower()
        lines = block.split("\n")
        
        # -------------------------------------------------------------------------
        # ALUR 1: LOGIKA UNIVERSAL LAMA (TEKS JELAS & ADA KATA KUNCI PEMBELAAN)
        # -------------------------------------------------------------------------
        if "not found" in block_lower or "missing" in block_lower or "found" in block_lower:
            
            # --- DETEKSI FORMAT VERTIKAL / STRUCTURED FORM ---
            is_vertical_format = any(":" in line.strip() and not line.strip().startswith(tuple(str(i) for i in range(10))) for line in lines)
            
            if is_vertical_format:
                loc_val, bin_val, pn_val, sn_val, qty_val, remark_val = "-", "-", "-", "-", 1, "-"
                additional_remark = ""
                has_pn_vertical = False
                
                finding_no = ""
                find_match = re.search(r'(?:Finding No|No Finding|No\.)\s*(\d+)', block, re.IGNORECASE)
                if find_match and not find_match.group(0).upper().startswith("PN"):
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
                            pn_clean_match = re.search(r'([A-Za-z0-9\-/.\s]+)', val)
                            pn_val = pn_clean_match.group(1).strip() if pn_clean_match else val
                            if val != "-" and val != "":
                                has_pn_vertical = True
                        elif "SN" in key: 
                            sn_val = val
                        elif "QTY ACT" in key or "QTY ACTUAL" in key or "QTY" in key:
                            qty_match = re.search(r'(\d+)', val)
                            if qty_match: qty_val = int(qty_match.group(1))
                        elif "REMARK" in key: 
                            remark_val = val

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
                
                remark_val = finding_no + remark_val + action_remark + additional_remark

                if has_pn_vertical and pn_val != "-":
                    item = {"Loc": loc_val, "BIN": bin_val, "PN": pn_val, "SN": sn_val, "Quantity": qty_val, "Remark": remark_val}
                    parsed_data.append(item)
                    # Catat ke history untuk cadangan backtrack jika statusnya komplain (bukan resolve murni harian)
                    if "NOT FOUND" in block_upper or "MISSING" in block_upper:
                        complaint_history.append(item)
                
            else:
                # --- FORMAT HORIZONTAL / BORONGAN TEKS BEBAS ---
                clean_block = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*[^:]+:\s*', '', block, flags=re.IGNORECASE)
                clean_lines = clean_block.split("\n")
                
                bin_global = "-"
                remark_global = "Found"
                
                for line in clean_lines:
                    line_upper = line.upper()
                    if any(k in line_upper for k in ["FOUND AT", "TRANSFER BIN", "TRANSFER TO"]):
                        bin_match = re.search(r'\b([A-Za-z0-9\s]+-[A-Za-z0-9\s\-]+)\b', line)
                        if bin_match:
                            raw_bin = bin_match.group(1).strip()
                            if "BIN " in raw_bin.upper():
                                raw_bin = raw_bin.upper().split("BIN ")[-1].strip()
                            bin_global = raw_bin
                            break
                
                if bin_global == "-":
                    for line in clean_lines:
                        bin_match = re.search(r'\b(?:BIN|FOUND AT|DI BIN)\s*#?\s*([A-Za-z0-9\s\-]{2,20})', line, re.IGNORECASE)
                        if bin_match:
                            potential_bin = bin_match.group(1).strip()
                            if not any(x in potential_bin.upper() for x in ["ACTUAL", "BIN", "FOUND", "OMITTED", "PLACED", "DISPSL"]):
                                bin_global = potential_bin
                                break
                            
                if "FOUND AT " in bin_global.upper():
                    bin_global = bin_global.upper().split("FOUND AT ")[-1].replace("BIN ", "").strip()
                
                loc_global = bin_global.split("-")[0] if "-" in bin_global else "-"
                
                for line in reversed(clean_lines):
                    if any(k in line.upper() for k in ["FOUND", "TRANSFER", "ISSUED", "REMARK"]):
                        remark_global = line.strip()
                        break
                
                for line in clean_lines:
                    if any(x in line.upper() for x in ["PN#", "PN ", "PART NUMBER"]):
                        pn_match = re.search(r'(?:PN#|PN|Part\s*Number)[:\s-]*([A-Za-z0-9\-/.\s]+)', line, re.IGNORECASE)
                        sn_match = re.search(r'(?:SN#|SN|Serial|S/N)[:\s-]*([A-Za-z0-9\-]+)', line, re.IGNORECASE)
                        qty_match = re.search(r'(?:QTY#|QTY)[:\s-]*(\d+)|(\d+)\s*(?:pcs|qty|item)', line, re.IGNORECASE)
                        
                        if qty_match:
                            qty_val = int(qty_match.group(1)) if qty_match.group(1) else int(qty_match.group(2))
                        else:
                            qty_val = 1
                            
                        item = {"Loc": loc_global, "BIN": bin_global, "PN": pn_match.group(1).strip() if pn_match else "-", "SN": sn_match.group(1).strip() if sn_match else "-", "Quantity": qty_val, "Remark": remark_global}
                        parsed_data.append(item)
                        if "NOT FOUND" in block_lower or "missing" in block_lower:
                            complaint_history.append(item)

        # -------------------------------------------------------------------------
        # ALUR 2: LOGIKA EMERGENCY (STASIUN PARAH - BOM FOTO KOSONGAN TANPA TEKS)
        # -------------------------------------------------------------------------
        elif "<media omitted>" in block_lower and not any(k in block_lower for k in ["pn", "sn", "part"]):
            # Jika ada riwayat komplain di atasnya, ambil data komplain terakhir sebagai target penemuan gambar ini
            if complaint_history:
                last_complaint = complaint_history[-1] # Ambil komplain terdekat di atasnya
                
                parsed_data.append({
                    "Loc": last_complaint["Loc"],
                    "BIN": last_complaint["BIN"],
                    "PN": last_complaint["PN"],
                    "SN": last_complaint["SN"],
                    "Quantity": last_complaint["Quantity"],
                    "Remark": f"Resolved via Photo Evidence (Automatic Timeline Radius Match) 📸"
                })

    if parsed_data:
        df_raw = pd.DataFrame(parsed_data)
        
        # Tameng filter surplus / minus harian murni tanpa status pencarian barang
        def filter_strict_pembelaan(row):
            rem = str(row['Remark']).upper()
            if any(trash in rem for trash in ["SURPLUS", "MINUS", "WRONG BINNING", "UNRECORDED"]) and "PHOTO" not in rem:
                return False
            return True

        df_filtered = df_raw[df_raw.apply(filter_strict_pembelaan, axis=1)]
        
        # Pembersihan potongan string kotor di kolom BIN
        def clean_final_bins(val):
            v_upper = str(val).upper().strip()
            if v_upper in ["A", "PLACED", "OMITTED", "MEDIA", "<MEDIA", "FOUND", "ACTUAL", "BIN", "ACTUAL BIN", "-"]:
                return "-"
            if "BIN " in v_upper:
                val = str(val).upper().split("BIN ")[-1].strip()
            return val
            
        df_filtered['BIN'] = df_filtered['BIN'].apply(clean_final_bins)
        
        # Sinkronisasi ulang kolom Loc pasca-pembersihan BIN
        def sync_clean_loc(row):
            b_val = str(row['BIN'])
            l_val = str(row['Loc'])
            if "-" in b_val and l_val == "-":
                return b_val.split("-")[0].strip()
            return l_val

        df_filtered['Loc'] = df_filtered.apply(sync_clean_loc, axis=1)
        
        # Rekonsiliasi data duplikat update chat (keep='last')
        df = df_filtered.drop_duplicates(subset=["BIN", "PN", "SN"], keep="last").reset_index(drop=True)
        
        st.success(f"🎉 Sukses Besar! Kodingan Kompatibilitas Tinggi Berhasil Diluncurkan. Total data valid: {len(df)} baris.")
        st.dataframe(df, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Audit_Findings_Found')
            
        st.markdown("### 📥 Download File Excel Hasil Gabungan")
        st.download_button(
            label="📊 Download File Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="rekap_pembelaan_ultimate_universal.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
