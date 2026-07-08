import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(
    page_title="WhatsApp Automated Audit to Excel",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ WhatsApp Automated Audit Extractor (Strict Discrepancy Filter)")
st.write("Versi Steril 100%: Memblokir total temuan murni SURPLUS, MINUS, atau WRONG BINNING harian yang tidak berkaitan dengan kasus barang Hilang / Not Found.")

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
        lines = block.split("\n")
        
        # Cek apakah blok ini merupakan format teks vertikal terstruktur (ada properti titik dua)
        is_vertical_format = any(":" in line.strip() and not line.strip().startswith(tuple(str(i) for i in range(10))) for line in lines)
        
        if is_vertical_format:
            loc_val, bin_val, pn_val, sn_val, qty_val, remark_val = "-", "-", "-", "-", 1, "-"
            additional_remark = ""
            
            # Ekstraksi isi form internal vertikal
            for line in lines:
                line_clean = line.strip()
                if ":" in line_clean and not line_clean.startswith(tuple(str(i) for i in range(10))):
                    parts = line_clean.split(":", 1)
                    key = parts[0].strip().upper()
                    val = parts[1].strip()
                    
                    if "LOC" in key: loc_val = val
                    elif "BIN EMRO" in key: bin_val = val
                    elif "BIN ACTUAL" in key or "BIN ACT" in key: bin_val = val
                    elif "BIN" in key and bin_val == "-": bin_val = val
                    elif "PN" in key: pn_val = val
                    elif "SN" in key: sn_val = val
                    elif "QTY ACT" in key or "QTY ACTUAL" in key:
                        qty_match = re.search(r'(\d+)', val)
                        if qty_match: qty_val = int(qty_match.group(1))
                    elif "QTY EMRO" in key and qty_val == 1:
                        qty_match = re.search(r'(\d+)', val)
                        if qty_match: qty_val = int(qty_match.group(1))
                    elif "REMARK" in key: remark_val = val

            # Grab catatan kaki / kalimat update penyelesaian di bawah form vertikal jika ada
            for line in lines:
                if "PENYELESAIAN" in line.upper() or line.strip().startswith("*"):
                    additional_remark = " " + line.strip().replace("*", "")
                    break
            
            if remark_val == "-" or remark_val == "": remark_val = "Found"
            if additional_remark: remark_val = remark_val + additional_remark
            
            # === TAMENG UTAMA: FILTER KETAT FORMAT VERTIKAL ===
            # Jika baris remark murni diisi SURPLUS, MINUS, atau WRONG BINNING biasa tanpa ada riwayat ditemukannya barang hilang, skip!
            rem_upper = remark_val.upper()
            if any(x in rem_upper for x in ["SURPLUS", "MINUS", "WRONG BINNING"]) and not any(y in rem_upper for y in ["FOUND", "MISSING", "NOT FOUND"]):
                continue
                
            # Pastikan teks balon chat secara keseluruhan memang valid bagian dari dispute barang hilang
            if not any(k in block_lower for k in ["not found", "missing", "found"]):
                continue

            parsed_data.append({
                "Loc": loc_val, "BIN": bin_val, "PN": pn_val, "SN": sn_val, "Quantity": qty_val, "Remark": remark_val
            })
            
        else:
            # FORMAT HORIZONTAL / BORONGAN BANYAK ITEM (PN# , SN#)
            # Saring ketat agar format horizontal liar di luar grup penemuan tidak ikut kesedot
            if not any(k in block_lower for k in ["not found", "found", "missing"]):
                continue
                
            clean_block = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s*-\s*[^:]+:\s*', '', block, flags=re.IGNORECASE)
            clean_lines = clean_block.split("\n")
            
            bin_global = "-"
            remark_global = "Found"
            
            # Cari baris lokasi BIN
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
            
            # Ambil kalimat pembelaan paling bawah secara dinamis sebagai Remark
            for line in reversed(clean_lines):
                if any(k in line.upper() for k in ["FOUND", "TRANSFER", "ISSUED", "REMARK"]):
                    remark_global = line.strip()
                    break
            
            # Proteksi konten horizontal dari kata kunci surplus murni
            if "surplus" in remark_global.lower() and not any(x in remark_global.lower() for x in ["found", "missing"]):
                continue
            
            has_items = False
            for line in clean_lines:
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
        # Rekonsiliasi duplikat, ambil update paling terakhir (keep last)
        df = df_raw.drop_duplicates(subset=["BIN", "PN", "SN"], keep="last").reset_index(drop=True)
        
        st.success(f"🎉 Sukses Steril! Berhasil membersihkan total riwayat. Data final: {len(df)} baris.")
        st.dataframe(df, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Audit_Findings_Found')
            
        st.markdown("### 📥 Download File Excel Hasil Saringan")
        st.download_button(
            label="📊 Download File Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="rekap_pembelaan_steril.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
