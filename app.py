import pandas as pd
import streamlit as st

st.set_page_config(page_title="Stock Opname Matcher", layout="wide")
st.title("📦 Stock Opname Discrepancy Matcher")

# 1. Gunakan cache data agar proses file yang di-upload tidak di-load berulang-ulang saat di-refresh
@st.cache_data
def load_and_process_data(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    data_sheets = [sheet for sheet in xls.sheet_names if 'DATA' in sheet.upper()]
    
    all_results = {}
    
    for sheet in data_sheets:
        df = pd.read_excel(xls, sheet_name=sheet)
        df.columns = df.columns.str.strip()
        
        required_cols = {'PN', 'BIN', 'Result'}
        if not required_cols.issubset(df.columns):
            continue
            
        df['PN'] = df['PN'].astype(str).str.strip()
        df['BIN'] = df['BIN'].astype(str).str.strip()
        df['Result'] = df['Result'].astype(str).str.strip().str.upper()
        
        target_results = {'SURPLUS', 'MINUS', 'NOT FOUND', 'UNRECORD', 'UNRECORDED', 'FOUND'}
        df_filtered = df[df['Result'].isin(target_results)].copy()
        
        # Logika matching cepat per kelompok PN
        pn_results = df_filtered.groupby('PN')['Result'].transform(lambda x: [set(x)] * len(x))
        
        def check_pair(res_set):
            has_surplus_minus = 'SURPLUS' in res_set and 'MINUS' in res_set
            has_surplus_found = 'SURPLUS' in res_set and any(r in res_set for r in ['NOT FOUND', 'FOUND'])
            has_unrec_notfound = any(r in res_set for r in ['UNRECORD', 'UNRECORDED']) and any(r in res_set for r in ['NOT FOUND', 'FOUND'])
            has_unrec_minus    = any(r in res_set for r in ['UNRECORD', 'UNRECORDED']) and 'MINUS' in res_set
            return has_surplus_minus or has_surplus_found or has_unrec_notfound or has_unrec_minus

        is_matched = pn_results.apply(check_pair)
        df_matched = df_filtered[is_matched].copy()
        
        if not df_matched.empty:
            cols_to_show = ['PN', 'BIN', 'Result']
            qty_emro_col = 'Qty eMRO' if 'Qty eMRO' in df_matched.columns else ('QTY Available' if 'QTY Available' in df_matched.columns else None)
            qty_act_col = 'Qty Actual' if 'Qty Actual' in df_matched.columns else None
            
            if qty_emro_col: cols_to_show.append(qty_emro_col)
            if qty_act_col: cols_to_show.append(qty_act_col)
            
            all_results[sheet] = df_matched[cols_to_show]
            
    return all_results

# --- UI STREAMLIT (INPUT MANUAL USER) ---
# Tombol upload dipasang di sini, jadi aplikasi ga bakal jalan sebelum file di-drop
uploaded_file = st.file_uploader("Upload File Excel Stock Opname (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    st.info(f"📂 File terbaca: `{uploaded_file.name}`")
    
    with st.spinner("Sedang memproses dan mencari pasangan discrepancy... Mohon tunggu..."):
        processed_data = load_and_process_data(uploaded_file)
    
    if processed_data:
        for sheet_name, df_res in processed_data.items():
            st.write(f"### 📊 Hasil Pasangan untuk Sheet: **{sheet_name}**")
            st.dataframe(df_res, use_container_width=True)
            st.markdown("---")
    else:
        st.warning("❌ Tidak ditemukan pasangan matching discrepancy di file ini.")
else:
    st.write("👋 Silakan upload file Excel lo terlebih dahulu untuk memulai analisis.")
