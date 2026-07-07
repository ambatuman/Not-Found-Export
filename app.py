import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(
    page_title="WhatsApp Automated Audit to Excel",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ WhatsApp Automated Audit Extractor (Anti-Double & Full Remark)")
st.write("Versi mutakhir: Memperbaiki bug data double dan menarik isi **REMARKS** asli dari chat WhatsApp secara utuh.")

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
        # Ambil semua chat yang mengandung unsur temuan/pembelaan audit
        if "not found" in block_lower or "found" in block_lower or "surplus" in block_lower or "minus" in block_lower:
            lines = block.split("\n")
            
            # Cek apakah blok chat ini menggunakan format rapi vertikal (ada 'LOC :', 'PN :', dll)
            is_vertical_format = any(":" in line.strip() and not line.strip().startswith(tuple(str(i) for i in range(10))) for line in lines)
            
            if is_vertical_format:
                loc_val, bin_val, pn_val, sn_val, qty_val, remark_val = "-", "-", "-", "-", 1, "-"
                
                for line in lines:
                    line_clean = line.strip()
                    if ":" in line_clean:
                        parts = line_clean.split(":", 1)
                        key = parts[0].strip().upper()
                        val = parts[1].strip()
                        
                        if "LOC" in key: 
                            loc_val = val
                        elif "BIN" in key: 
                            bin_val = val
                        elif "PN" in key: 
                            pn_val = val
                        elif "SN" in key: 
                            sn_val = val
                        elif "QTY ACT" in key: # Prioritaskan Quantity Actual di lapangan
                            qty_match = re.search(r'(\d+)', val)
                            if qty_match: qty_val = int(qty_match.group(1))
                        elif "QTY EMRO" in key and qty_val == 1: # Fallback ke Qty Emro jika Qty Act belum terbaca
                            qty_match = re.search(r'(\d+)', val)
                            if qty_match: qty_val = int(qty_match.group(1))
                        elif "REMARK" in key: # Menangkap REMARKS asli dari chat secara utuh!
                            remark_val = val

                # Jika di baris REMARK tidak ada isi, cari baris alternatif bawah (Penyelesaian/*)
                if remark_val == "-" or remark_val == "":
                    for line in lines:
                        if "Penyelesaian" in line or line.strip().startswith("*"):
                            remark_val = line.replace("*", "").replace("Penyelesaian :", "").strip()
                            break
                
                if remark_val == "-":
                    remark_val = "Found"

                parsed_data.append({
                    "Loc": loc_val,
                    "BIN": bin_val,
                    "PN": pn_val,
                    "SN": sn_val,
                    "Quantity": qty_val,
                    "Remark": remark_val
                })
                
            else:
                # FORMAT HORIZONTAL / BORONGAN (PN# , SN#)
                # Kunci agar tidak double jika formatnya teks bebas biasa
                bin_match = re.search(r'\b([A-Za-z0-9]+-[A-Za-z0-9\-]+)\b', block)
                if not bin_match:
                    bin_match = re.search(r'(?:BIN|AT|DI)\s*#?\s*([A-Za-z0-9\-]+)', block, re.IGNORECASE)
                
                bin_global = bin_match.group(1).strip() if bin_match else "-"
                if bin_global.upper() in ["BIN", "AT", "DI", "FOUND"]:
                    secondary_match = re.search(r'(?:BIN|AT|DI)\s+(?:BIN|AT|DI)\s+([A-Za-z0-9\-]+)', block, re.IGNORECASE)
                    if secondary_match: bin_global = secondary_match.group(1).strip()
                
                loc_global = bin_global.split("-")[0] if "-" in bin_global else "-"
                
                remark_global = f"Found at {bin_global}"
                for line in lines:
                    if any(x in line.upper() for x in ["TRANSFER TO", "ISSUED BY", "TOOL FOUND AT", "REMARK"]):
                        if ":" in line:
                            remark_global = line.split(":", 1)[1].strip()
                        else:
                            remark_global = line.strip()
                        break
                
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
                            "Loc": loc_global, "BIN": bin_global, "PN": pn_match.group(1).strip() if pn_match else "-", "SN": sn_match.group(1).strip() if sn_match else "-", "Quantity": qty_val, "Remark": remark_global
                        })
                        
                if not has_items:
                    parsed_data.append({
                        "Loc": loc_global, "BIN": bin_global, "PN": "-", "SN": "-", "Quantity": 1, "Remark": block.strip()[:150]
                    })

    if parsed_data:
        # Menghapus duplikasi baris data yang sama persis agar tidak ada double input
        df = pd.DataFrame(parsed_data).drop_duplicates().reset_index(drop=True)
        
        st.success(f"🎉 Sukses! Berhasil memproses data chat tanpa duplikat. Total terdeteksi: {len(df)} baris data.")
        st.dataframe(df, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Audit_Findings_Found')
            
        st.markdown("### 📥 Download File Excel Lu")
        st.download_button(
            label="📊 Download File Excel Langsung (.xlsx)",
            data=buffer.getvalue(),
            file_name="rekap_pembelaan_clean.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
