import streamlit as st
import pandas as pd
import io

# Setup halaman aplikasi
st.set_page_config(
    page_title="WhatsApp Audit Text to Excel",
    page_icon="📊",
    layout="wide"
)

st.title("📊 WhatsApp Audit Text to Excel & Reply Generator")
st.write("Upload file `.txt` hasil ekspor chat WhatsApp untuk mendeteksi temuan **'not found'** dan mengisinya menjadi file Excel siap pakai.")

st.divider()

# 1. Fitur Upload File .txt WhatsApp
uploaded_file = st.file_uploader("Pilih file chat WhatsApp (.txt)", type=["txt"])

if uploaded_file is not None:
    # Membaca file text chat WhatsApp
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    chat_lines = stringio.readlines()
    
    st.success(f"📂 Berhasil memuat {len(chat_lines)} baris chat.")
    
    # Proses pencarian kata "not found" secara otomatis (case-insensitive)
    findings = []
    for idx, line in enumerate(chat_lines):
        if "not found" in line.lower():
            clean_text = line.strip()
            
            # Coba ambil isi chat-nya saja dengan memisahkan nama pengirim jika formatnya standar
            if " - " in clean_text and ":" in clean_text:
                parts = clean_text.split(":", 1)
                msg_content = parts[1].strip() if len(parts) > 1 else clean_text
            elif "]" in clean_text and ":" in clean_text:
                parts = clean_text.split(":", 2)
                msg_content = parts[-1].strip() if len(parts) > 0 else clean_text
            else:
                msg_content = clean_text
                
            findings.append({
                "Line": idx + 1,
                "Original Chat": clean_text,
                "Extracted Finding": msg_content
            })
            
    if not findings:
        st.warning("📭 Tidak ditemukan chat dengan kata kunci 'not found' di dalam file ini.")
    else:
        st.markdown(f"### 🔍 Terdeteksi {len(findings)} temuan 'Not Found'")
        
        # Simpan database data audit di session state agar tidak hilang saat halaman re-run/refresh tombol
        if 'audit_data' not in st.session_state:
            st.session_state.audit_data = pd.DataFrame(columns=["Loc", "BIN", "PN", "SN", "Quantity", "Remark"])
            
        # Dropdown untuk memilih finding mana yang mau dijawab/dimasukkan data barangnya
        selected_finding_idx = st.selectbox(
            "Pilih chat finding yang ingin diproses:",
            options=range(len(findings)),
            format_func=lambda x: f"Baris {findings[x]['Line']}: {findings[x]['Extracted Finding'][:80]}..."
        )
        
        chosen_finding = findings[selected_finding_idx]
        st.info(f"📌 **Chat Auditor Terpilih:**\n{chosen_finding['Original Chat']}")
        
        # Form Input untuk Pengisian Data Excel & Pembelaan Auditee
        st.markdown("### 📝 Pengisian Detail Barang Ditemukan (Found)")
        
        col1, col2 = st.columns(2)
        with col1:
            loc = st.text_input("🏢 Lokasi Gudang / Area (Loc)", placeholder="Contoh: WH-Jakarta Pusat")
            bin_loc = st.text_input("📍 Lokasi BIN", placeholder="Contoh: BIN-A01")
            pn = st.text_input("🔢 Part Number (PN)", placeholder="Contoh: PN-99281-X")
            
        with col2:
            sn = st.text_input("🏷️ Serial Number (SN) - Jika Ada", placeholder="Contoh: SN-102938 (Kosongkan jika tidak ada)")
            qty = st.number_input("📦 Quantity", min_value=1, value=1, step=1)
            remark = st.text_area("💬 Remark Keterangan Found", placeholder="Contoh: Barang ditemukan terselip di bawah box inner, sudah diletakkan kembali ke bin.")
            
        # Tombol Masukkan Data ke Tabel Sementara
        if st.button("➕ Tambahkan ke Tabel Excel", type="primary"):
            if not bin_loc or not pn:
                st.error("⚠️ Mohon isi minimal data **BIN** dan **Part Number (PN)**!")
            else:
                new_row = {
                    "Loc": loc if loc else "-",
                    "BIN": bin_loc,
                    "PN": pn,
                    "SN": sn if sn else "-",
                    "Quantity": qty,
                    "Remark": remark if remark else "Found sesuai item"
                }
                # Memasukkan data baru ke dataframe session state
                st.session_state.audit_data = pd.concat([st.session_state.audit_data, pd.DataFrame([new_row])], ignore_index=True)
                st.success("✅ Data berhasil dimasukkan ke tabel sementara di bawah!")
                
        # Tampilkan Preview Tabel Hasil Rekapan
        st.markdown("---")
        st.markdown("### 📋 Preview Tabel Data Hasil Export")
        
        if not st.session_state.audit_data.empty:
            st.dataframe(st.session_state.audit_data, use_container_width=True)
            
            # Convert Dataframe ke format Excel di dalam memori buffer
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                st.session_state.audit_data.to_excel(writer, index=False, sheet_name='Audit_Findings_Found')
            
            col_dl, col_reset = st.columns([1, 5])
            with col_dl:
                # Tombol Download File Excel .xlsx
                st.download_button(
                    label="📥 Download Data Excel (.xlsx)",
                    data=buffer.getvalue(),
                    file_name="rekap_finding_found.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with col_reset:
                # Tombol Reset Data jika ingin mengulang dari awal
                if st.button("🗑️ Reset / Hapus Semua Baris"):
                    st.session_state.audit_data = pd.DataFrame(columns=["Loc", "BIN", "PN", "SN", "Quantity", "Remark"])
                    st.rerun()
                
            # BONUS: Otomatis buatin template chat buat langsung lu copy ke WA grup
            st.markdown("### 💬 Bonus: Format Teks Balasan WA (Baris Terakhir Terinput)")
            last_row = st.session_state.audit_data.iloc[-1]
            sn_wa = f"\n* *SN:* {last_row['SN']}" if last_row['SN'] != "-" else ""
            
            whatsapp_reply = (
                f"✅ *Status update untuk temuan: NOT FOUND*\n\n"
                f"Halo Auditor, mohon izin menginfokan bahwa barang di lokasi *{last_row['Loc']}* saat ini **SUDAH DITEMUKAN (FOUND)** dengan detail sebagai berikut:\n\n"
                f"* *BIN:* {last_row['BIN']}\n"
                f"* *PN:* {last_row['PN']}{sn_wa}\n"
                f"* *QTY:* {last_row['Quantity']}\n\n"
                f"*Remarks:* {last_row['Remark']}\n\n"
                f"Mohon untuk dapat di-update pada sistem / data audit. Terima kasih! 🙏"
            )
            st.text_area("Copy teks ini untuk langsung reply ke grup WA:", value=whatsapp_reply, height=180)
            st.caption("💡 *Tips: Klik ikon dua kotak di pojok kanan atas kolom teks di atas untuk menyalin cepat.*")
        else:
            st.info("Tabel output Excel masih kosong. Silakan isi form di atas dan klik 'Tambahkan ke Tabel Excel' terlebih dahulu.")
