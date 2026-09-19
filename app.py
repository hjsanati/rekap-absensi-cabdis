import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import io

st.set_page_config(page_title="E-Absensi Cabdis", page_icon="🏫", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { color: #1e3a8a; }
    .stButton>button { background-color: #1e3a8a; color: white; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'role' not in st.session_state: st.session_state.role = None
if 'unit_kerja' not in st.session_state: st.session_state.unit_kerja = None

@st.cache_data
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Rekap Absen')
    return output.getvalue()

def login_page():
    st.title("E-Absensi Cabdis Wilayah IV")
    st.markdown("Silakan login menggunakan akun yang telah terdaftar.")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        if submit:
            response = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
            if len(response.data) > 0:
                user = response.data[0]
                st.session_state.logged_in = True
                st.session_state.role = user['role']
                st.session_state.unit_kerja = user['unit_kerja']
                st.session_state.nama = user['nama']
                st.rerun()
            else:
                st.error("Username atau Password salah!")

def menu_dashboard():
    st.header("Dashboard Realtime Cabdis")
    st.info("Daftar sekolah yang telah melakukan penginputan rekap absensi.")
    col1, col2 = st.columns(2)
    bulan = col1.selectbox("Pilih Bulan", list(range(1, 13)), index=datetime.now().month - 1)
    tahun = col2.number_input("Tahun", min_value=2020, max_value=2050, value=datetime.now().year)
    
    st.write("---")
    res_absen = supabase.table("absensi").select("pegawai_id").eq("bulan", bulan).eq("tahun", tahun).execute()
    if res_absen.data:
        df_absen = pd.DataFrame(res_absen.data)
        res_peg = supabase.table("pegawai").select("id, unit_kerja").execute()
        if res_peg.data:
            df_gabung = pd.merge(df_absen, pd.DataFrame(res_peg.data), left_on='pegawai_id', right_on='id')
            sekolah_sudah = df_gabung['unit_kerja'].dropna().unique()
            st.subheader(f"Total: {len(sekolah_sudah)} Sekolah")
            for sek in sorted(sekolah_sudah): st.success(f"✅ {sek} telah melakukan penginputan")
    else:
        st.warning(f"Belum ada data absensi yang masuk pada bulan {bulan} tahun {tahun}.")

def menu_data_pegawai():
    st.header(f"Data Pegawai - {st.session_state.unit_kerja}")
    with st.expander("Tambah Pegawai Baru"):
        with st.form("form_pegawai"):
            nama = st.text_input("Nama Pegawai")
            nip = st.text_input("NIP")
            gol = st.text_input("Golongan")
            status = st.selectbox("Status", ["PNS", "PPPK", "PPPK PW"])
            if st.form_submit_button("Simpan Pegawai"):
                supabase.table("pegawai").insert({"nama": nama, "nip": nip, "golongan": gol, "status": status, "unit_kerja": st.session_state.unit_kerja}).execute()
                st.success("Pegawai berhasil ditambahkan!")
                st.rerun()
                
    st.subheader("Daftar Pegawai")
    response = supabase.table("pegawai").select("*").eq("unit_kerja", st.session_state.unit_kerja).execute()
    if response.data: st.dataframe(pd.DataFrame(response.data), use_container_width=True)

def menu_input_absen(jenis_pegawai):
    st.header(f"Input Rekap Absensi - {jenis_pegawai}")
    col1, col2 = st.columns(2)
    bulan = col1.selectbox("Pilih Bulan", list(range(1, 13)), index=datetime.now().month - 1)
    tahun = col2.number_input("Tahun", min_value=2020, max_value=2050, value=datetime.now().year)
    
    # Tarik data pegawai
    res_peg = supabase.table("pegawai").select("id, nama, nip").eq("unit_kerja", st.session_state.unit_kerja)
    if jenis_pegawai == "PNS": res_peg = res_peg.eq("status", "PNS").execute()
    else: res_peg = res_peg.in_("status", ["PPPK", "PPPK PW"]).execute()
    
    if not res_peg.data:
        st.warning(f"Belum ada data pegawai {jenis_pegawai} di sekolah ini.")
        return
        
    df_peg = pd.DataFrame(res_peg.data)
    pegawai_ids = df_peg['id'].tolist()
    
    # Tarik data absensi yang sudah ada
    res_abs = supabase.table("absensi").select("*").eq("bulan", bulan).eq("tahun", tahun).in_("pegawai_id", pegawai_ids).execute()
    df_abs = pd.DataFrame(res_abs.data) if res_abs.data else pd.DataFrame()
    
    is_locked = False
    if not df_abs.empty and 'is_locked' in df_abs.columns and df_abs['is_locked'].any():
        is_locked = True
            
    # Sinkronisasi data pegawai dengan absensi
    data_gabung = []
    for _, peg in df_peg.iterrows():
        abs_row = df_abs[df_abs['pegawai_id'] == peg['id']] if not df_abs.empty else pd.DataFrame()
        if not abs_row.empty:
            row = abs_row.iloc[0].to_dict()
            row['nama'], row['nip'] = peg['nama'], peg['nip']
        else:
            row = {'pegawai_id': peg['id'], 'nama': peg['nama'], 'nip': peg['nip'], 'hari_kerja': 0, 'hadir': 0, 'telat_masuk': 0, 'cepat_pulang': 0, 'tanpa_keterangan': 0, 'cuti_sakit_izin': 0, 'dinas_luar': 0, 'keterangan': ''}
        data_gabung.append(row)
        
    df_tampil = pd.DataFrame(data_gabung)
    kolom_tampil = ['nama', 'nip', 'hari_kerja', 'hadir', 'telat_masuk', 'cepat_pulang', 'tanpa_keterangan', 'cuti_sakit_izin', 'dinas_luar', 'keterangan']
    
    # Tombol Download
    excel_data = convert_df_to_excel(df_tampil[kolom_tampil])
    st.download_button(label="📥 Download Data ke Excel", data=excel_data, file_name=f"Rekap_{jenis_pegawai}_{bulan}_{tahun}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    if is_locked:
        st.error("🔒 Data bulan ini telah DILOCK / DIKUNCI PERMANEN. Hubungi Admin Cabdis jika ada kesalahan.")
        st.dataframe(df_tampil[kolom_tampil], use_container_width=True)
    else:
        st.info("💡 Ketik langsung pada tabel di bawah seperti menggunakan Excel. Jangan lupa klik tombol Simpan di bawah tabel.")
        edited_df = st.data_editor(df_tampil[kolom_tampil], disabled=['nama', 'nip'], use_container_width=True, num_rows="fixed")
        
        col_btn1, col_btn2 = st.columns(2)
        simpan_draf = col_btn1.button("💾 Simpan Sementara (Bisa diedit lagi)")
        simpan_kunci = col_btn2.button("🔒 Simpan & Kunci Permanen")
        
        if simpan_draf or simpan_kunci:
            supabase.table("absensi").delete().eq("bulan", bulan).eq("tahun", tahun).in_("pegawai_id", pegawai_ids).execute()
            new_data = []
            for i, row in edited_df.iterrows():
                new_data.append({
                    "pegawai_id": df_tampil.iloc[i]['pegawai_id'], "bulan": bulan, "tahun": tahun,
                    "hari_kerja": row['hari_kerja'], "hadir": row['hadir'], "telat_masuk": row['telat_masuk'],
                    "cepat_pulang": row['cepat_pulang'], "tanpa_keterangan": row['tanpa_keterangan'],
                    "cuti_sakit_izin": row['cuti_sakit_izin'], "dinas_luar": row['dinas_luar'],
                    "keterangan": row['keterangan'] if pd.notna(row['keterangan']) else "",
                    "is_locked": True if simpan_kunci else False
                })
            supabase.table("absensi").insert(new_data).execute()
            st.success("Data absensi berhasil diperbarui!")
            st.rerun()

def menu_buka_kunci():
    st.header("Buka Kunci Absensi Sekolah")
    res_sekolah = supabase.table("users").select("unit_kerja").eq("role", "admin_sekolah").execute()
    if not res_sekolah.data:
        st.warning("Belum ada akun sekolah terdaftar.")
        return
        
    sekolah = st.selectbox("Pilih Sekolah", list(set([s['unit_kerja'] for s in res_sekolah.data])))
    col1, col2 = st.columns(2)
    bulan = col1.selectbox("Bulan", list(range(1, 13)), index=datetime.now().month - 1)
    tahun = col2.number_input("Tahun", min_value=2020, max_value=2050, value=datetime.now().year)
    
    if st.button("Buka Kunci (Unlock)"):
        res_peg = supabase.table("pegawai").select("id").eq("unit_kerja", sekolah).execute()
        if res_peg.data:
            pegawai_ids = [p['id'] for p in res_peg.data]
            supabase.table("absensi").update({"is_locked": False}).eq("bulan", bulan).eq("tahun", tahun).in_("pegawai_id", pegawai_ids).execute()
            st.success(f"Berhasil membuka kunci absensi {sekolah}!")
        else:
            st.warning("Tidak ditemukan data pegawai untuk sekolah tersebut.")

def menu_indisipliner(jenis_pegawai):
    st.header(f"Data Indisipliner {jenis_pegawai}")
    col1, col2, col3 = st.columns(3)
    periode = col1.selectbox("Filter Periode", ["1 Bulan Terakhir", "1 Tahun Terakhir"])
    tahun_p = col2.number_input("Pilih Tahun", min_value=2020, max_value=2050, value=datetime.now().year)
    bulan_p = col3.selectbox("Pilih Bulan", list(range(1, 13)), index=datetime.now().month - 1) if periode == "1 Bulan Terakhir" else None

    query_peg = supabase.table("pegawai").select("*")
    if st.session_state.role == 'admin_sekolah': query_peg = query_peg.eq("unit_kerja", st.session_state.unit_kerja)
    res_peg = query_peg.eq("status", "PNS").execute() if jenis_pegawai == "PNS" else query_peg.in_("status", ["PPPK", "PPPK PW"]).execute()
    
    if not res_peg.data:
        st.warning(f"Belum ada data pegawai {jenis_pegawai}.")
        return
        
    query_abs = supabase.table("absensi").select("*").eq("tahun", tahun_p)
    if periode == "1 Bulan Terakhir": query_abs = query_abs.eq("bulan", bulan_p)
    res_abs = query_abs.execute()
    
    if not res_abs.data:
        st.info("Belum ada rekap absensi pada periode yang dipilih.")
        return
        
    df_abs_grouped = pd.DataFrame(res_abs.data).groupby('pegawai_id').agg({'hari_kerja': 'sum', 'hadir': 'sum', 'telat_masuk': 'sum', 'cepat_pulang': 'sum', 'tanpa_keterangan': 'sum', 'cuti_sakit_izin': 'sum', 'dinas_luar': 'sum', 'keterangan': lambda x: ' | '.join(set([str(i) for i in x if i]))}).reset_index()
    df_final = pd.merge(pd.DataFrame(res_peg.data), df_abs_grouped, left_on='id', right_on='pegawai_id', how='inner')
    
    if df_final.empty:
        st.info("Belum ada rekap absensi yang cocok.")
        return
        
    df_final = df_final.sort_values(by=['tanpa_keterangan', 'telat_masuk'], ascending=[False, False])
    df_final = df_final[['nama', 'nip', 'golongan', 'status', 'unit_kerja', 'hari_kerja', 'hadir', 'telat_masuk', 'cepat_pulang', 'tanpa_keterangan', 'cuti_sakit_izin', 'dinas_luar', 'keterangan']]
    df_final.columns = ['Nama', 'NIP', 'Gol', 'STATUS', 'UNIT KERJA', 'HARI KERJA', 'HADIR', 'TELAT MASUK', 'CEPAT PULANG', 'TANPA KETERANGAN', 'CUTI/SAKIT/IZIN', 'DINAS LUAR', 'KETERANGAN']
    df_final.index = range(1, len(df_final) + 1)
    
    excel_data = convert_df_to_excel(df_final)
    st.download_button(label="📥 Download Data Indisipliner", data=excel_data, file_name=f"Indisipliner_{jenis_pegawai}_{tahun_p}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.dataframe(df_final, use_container_width=True)

def menu_tambah_akun():
    st.header("Manajemen Akun Admin")
    with st.form("form_akun"):
        col1, col2 = st.columns(2)
        nama = col1.text_input("Nama Admin / Sekolah")
        username = col2.text_input("Username Login")
        unit_kerja = col1.text_input("Unit Kerja (Misal: SMAN 1 Makassar)")
        role = col2.selectbox("Jenis Akun", ["admin_sekolah", "admin_cabdis"])
        if st.form_submit_button("Buat Akun"):
            supabase.table("users").insert({"nama": nama, "username": username, "unit_kerja": unit_kerja, "role": role, "password": st.text_input("Password", type="password")}).execute()
            st.success("Akun berhasil dibuat!")
            st.rerun()
    res_akun = supabase.table("users").select("id, nama, username, unit_kerja, role").execute()
    if res_akun.data: st.dataframe(pd.DataFrame(res_akun.data), use_container_width=True)

if not st.session_state.logged_in:
    login_page()
else:
    with st.sidebar:
        st.title("Menu Navigasi")
        st.write(f"👋 Halo, {st.session_state.nama}")
        st.write(f"🏢 {st.session_state.unit_kerja}")
        st.divider()
        
        if st.session_state.role == 'admin_cabdis':
            pilihan = st.radio("Pilih Menu", ["Dashboard", "Buka Kunci Absensi", "Data Indisipliner PNS", "Data Indisipliner PPPK", "Tambah Akun Admin"])
        else:
            pilihan = st.radio("Pilih Menu", ["Data Pegawai", "Input Rekap PNS", "Input Rekap PPPK", "Data Indisipliner PNS", "Data Indisipliner PPPK"])
            
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.rerun()

    if pilihan == "Dashboard": menu_dashboard()
    elif pilihan == "Data Pegawai": menu_data_pegawai()
    elif pilihan == "Input Rekap PNS": menu_input_absen("PNS")
    elif pilihan == "Input Rekap PPPK": menu_input_absen("PPPK")
    elif pilihan == "Buka Kunci Absensi": menu_buka_kunci()
    elif pilihan == "Tambah Akun Admin": menu_tambah_akun()
    elif pilihan == "Data Indisipliner PNS": menu_indisipliner("PNS")
    elif pilihan == "Data Indisipliner PPPK": menu_indisipliner("PPPK")
