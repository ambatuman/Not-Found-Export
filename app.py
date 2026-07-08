import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(
    page_title="Indonesia Dynamic Audit Extractor",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ WhatsApp Automated Audit Extractor (Dynamic Classifier Engine)")
st.write("Versi Pintar Skala Nasional: Otomatis mengelompokkan temuan lapangan menjadi Found, Wrong Binning, Minus, Surplus, atau Still Not Found.")

st.divider()

uploaded_file = st.file_uploader("Upload file chat WhatsApp (.txt) station mana saja di sini:", type=["txt"])

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
        
        # Jaring semua chat yang mengandung unsur pencarian atau dispute SO
        has_substance = any(x in block_lower for x in ["pn", "pn#", "part", "sn", "sn#", "bin", "loc"])
        is_audit_chat = any(x in block_lower for x in ["not found", "missing", "found", "minus", "surplus", "rts", "transfer", "actual"])
        
        if has_substance and is_audit_chat:
            
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
                        elif "REMARK" in key or "REMAKS" in key: 
                            remark_val = val

                # Tangkap baris kalimat ketikan santai dari tim store di bawah format titik dua
                action_text_lines = []
                for line in lines:
                    line_upper = line.upper()
                    # Ambil baris teks bebas yang bukan struktur utama dan bukan timestamp metadata
                    if ":" not in line and line.strip() and not line.strip().startswith("*") and not "OMITTED" in line_upper:
                        action_text_lines.append(line.strip())
                    elif "PENYELESAIAN" in line_upper or "ACTUAL" in line_upper or "DIPAKAI" in line_upper or "RTS" in line_upper:
                        if "QTY ACTUAL" not in line_upper:
                            action_text_lines.append(line.strip())

                action_remark = " ".join(action_text_lines).strip()
                
                if remark_val == "-" or remark_val == "": 
                    remark_val = "NOT FOUND"
                
                if action_remark:
                    remark_val = remark_val + " | Teks Lapangan: " + action_remark
                
                remark_val = finding_no + remark_val

                if has_pn_vertical and pn_val != "-":
                    parsed_data.append({
                        "Loc": loc_val, "BIN": bin_val, "PN": pn_val, "SN": sn_val, "Quantity": qty_val, "Remark": remark_val
                    })
                
            else:
                # --- FORMAT HORIZONTAL / BORONGAN TEKS BEBAS (LAMA) ---
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
                            
                        parsed_data.append({
                            "Loc": loc_global, "BIN": bin_global, "PN": pn_match.group(1).strip() if pn_match else "-", "SN": sn_match.group(1).strip() if sn_match else "-", "Quantity": qty_val, "Remark": remark_global
                        })

    if parsed_data:
        df_raw = pd.DataFrame(parsed_data)
        
        # Saring awal dari baris teks instruksi/siluman palsu
        df_raw = df_raw[~df_raw['PN'].str.upper().str.contains("DAN SN|CONTOH|PART NUMBER", na=False)]
        df_raw = df_raw[df_raw['PN'].str.len() > 2]
        
        # Pembersihan string kotor di kolom BIN
        def clean_final_bins(val):
            v_upper = str(val).upper().strip()
            if v_upper in ["A", "PLACED", "OMITTED", "MEDIA", "<MEDIA", "FOUND", "ACTUAL", "BIN", "ACTUAL BIN", "-"]:
                return "-"
            if "BIN " in v_upper:
                val = str(val).upper().split("BIN ")[-1].strip()
            return val
            
        df_raw['BIN'] = df_raw['BIN'].apply(clean_final_bins)
        
        # === BRAIN ENGINE: AUTOMATIC DISCREPANCY CLASSIFIER ===
        def classify_audit_status(row):
            rem = str(row['Remark']).upper()
            
            # 1. Deteksi Klasifikasi WRONG BINNING / TRANSFER RAK
            if any(w in rem for word in ["RTS", "TF", "TRANSFER", "PINDAH", "DI RCM", "DI CS", "REPAIR"]):
                return "WRONG BINNING / TRANSFER"
                
            # 2. Deteksi Klasifikasi MINUS / PARTIAL FOUND
            if "MINUS" in rem or "KURANG" in rem:
                return "MINUS / PARTIAL FOUND"
                
            # 3. Deteksi Klasifikasi SURPLUS
            if "SURPLUS" in rem or "LEBIH" in rem:
                return "SURPLUS"
                
            # 4. Deteksi Klasifikasi FOUND / MATCH VALID
            if any(w in rem for w in ["FOUND AT", "RESOLVED", "PENYELESAIAN", "FOUND ✅", "AKTUAL FOUND", "ACTUAL FOUND", "DIPAKAI USER", "TERPAKER", "MATCH"]):
                return "FOUND / RESOLVED"
                
            # 5. Fallback: Jika murni tidak ada teks jawaban, berarti masih berstatus hilang
            if "NOT FOUND" in rem or "MISSING" in rem:
                # Jika ada teks ketikan tambahan setelah tanda pipa '|', berarti storemen merespon sesuatu (bisa berupa status otonom)
                if "| TEKS LAPANGAN:" in rem and not any(x in rem for x in ["NOT FOUND", "MISSING"]):
                    return "FOUND / RESOLVED"
                return "STILL NOT FOUND"
                
            return "FOUND / RESOLVED"

        df_raw['Status Audit'] = df_raw.apply(classify_audit_status, axis=1)
        
        # Sinkronisasi ulang kolom Loc pasca-pembersihan BIN
        def sync_clean_loc(row):
            b_val = str(row['BIN'])
            l_val = str(row['Loc'])
            if "-" in b_val and l_val == "-":
                return b_val.split("-")[0].strip()
            return l_val

        df_raw['Loc'] = df_raw.apply(sync_clean_loc, axis=1)
        
        # Rekonsiliasi data duplikat harian (keep='last')
        df = df_raw.drop_duplicates(subset=["BIN", "PN", "SN"], keep="last").reset_index(drop=True)
        
        # Reorder kolom agar kolom 'Status Audit' ditaruh di depan agar mudah difilter user di Excel
        cols = ['Loc', 'BIN', 'PN', 'SN', 'Quantity', 'Status Audit', 'Remark']
        df = df[cols]
        
        st.success(f"🎉 Sempurna! Mesin Klasifikasi Otomatis Berhasil Memproses File Nasional. Total data: {len(df)} baris.")
        
        # Tampilkan visualisasi mini dashboard status audit agar Thariq mudah memantau
        st.markdown("### 📊 Ringkasan Status Hasil Audit Lapangan")
        status_counts = df['Status Audit'].value_counts()
        st.dataframe(status_counts, use_container_width=False)
        
        st.dataframe(df, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Audit_National_Summary')
            
        st.markdown("### 📥 Download File Master Rekap Indonesia")
        st.download_button(
            label="📊 Download File Excel Multi-Status (.xlsx)",
            data=buffer.getvalue(),
            file_name="rekap_master_audit_nasional_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
