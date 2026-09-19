import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

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

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'role' not in st.session_state:
    st.session_state.role = None
if 'unit_kerja' not in st.session_state:
    st.session_state.unit_kerja = None

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
    st.header("Dashboard Realtime")
    st.info("Menampilkan daftar sekolah yang telah menginput rekap absensi bulan ini.")
    st.write("*Visualisasi data atau tabel daftar sekolah akan muncul di sini.*")

def menu_data_pegawai():
    st.header(f"Data Pegawai - {st.session_state.unit_kerja}")
    
    with st.expander("Tambah Pegawai Baru"):
        with st.form("form_pegawai"):
            nama = st.text_input("Nama Pegawai")
            nip = st.text_input("NIP")
            gol = st.text_input("Golongan")
            status = st.selectbox("Status", ["PNS", "PPPK", "PPPK PW"])
            submit_pegawai = st.form_submit_button("Simpan Pegawai")
            
            if submit_pegawai:
                data = {
                    "nama": nama, "nip": nip, "golongan": gol, 
                    "status": status, "unit_kerja": st.session_state.unit_kerja
                }
                supabase.table("pegawai").insert(data).execute()
                st.success("Pegawai berhasil ditambahkan!")
                st.rerun()
                
    st.subheader("Daftar Pegawai")
    response = supabase.table("pegawai").select("*").eq("unit_kerja", st.session_state.unit_kerja).execute()
    if response.data:
        df = pd.DataFrame(response.data)
        st.dataframe(df, use_container_width=True)

def menu_input_absen(jenis_pegawai):
    st.header(f"Input Rekap Absensi - {jenis_pegawai}")
    
    bulan = st.selectbox("Pilih Bulan", list(range(1, 13)), index=datetime.now().month - 1)
    tahun = st.number_input("Tahun", min_value=2020, max_value=2050, value=datetime.now().year)
    
    if jenis_pegawai == "PNS":
        res = supabase.table("pegawai").select("id, nama, nip").eq("status", "PNS").eq("unit_kerja", st.session_state.unit_kerja).execute()
    else:
        res = supabase.table("pegawai").select("id, nama, nip").in_("status", ["PPPK", "PPPK PW"]).eq("unit_kerja", st.session_state.unit_kerja).execute()
    
    if not res.data:
        st.warning(f"Belum ada data pegawai {jenis_pegawai} di sekolah ini.")
        return

    st.write("Silakan input data rekap pada form di bawah:")
    with st.form(f"form_absen_{jenis_pegawai}"):
        pegawai_terpilih = st.selectbox("Pilih Pegawai", [f"{p['nama']} - {p['nip']}" for p in res.data])
        pegawai_id = res.data[[f"{p['nama']} - {p['nip']}" for p in res.data].index(pegawai_terpilih)]['id']
        
        col1, col2, col3, col4 = st.columns(4)
        hari_kerja = col1.number_input("Hari Kerja", min_value=0)
        hadir = col2.number_input("Hadir (Hari)", min_value=0)
        telat = col3.number_input("Telat Masuk (Menit)", min_value=0)
        cepat = col4.number_input("Cepat Pulang (Menit)", min_value=0)
        
        col5, col6, col7, col8 = st.columns(4)
        tk = col5.number_input("Tanpa Keterangan (Hari)", min_value=0)
        izin = col6.number_input("Cuti/Sakit/Izin (Hari)", min_value=0)
        dl = col7.number_input("Dinas Luar (Hari)", min_value=0)
        ket = col8.text_input("Keterangan")
        
        submit_absen = st.form_submit_button("Simpan Rekap")
        if submit_absen:
            absen_data = {
                "pegawai_id": pegawai_id, "bulan": bulan, "tahun": tahun,
                "hari_kerja": hari_kerja, "hadir": hadir, "telat_masuk": telat,
                "cepat_pulang": cepat, "tanpa_keterangan": tk, "cuti_sakit_izin": izin,
                "dinas_luar": dl, "keterangan": ket
            }
            supabase.table("absensi").insert(absen_data).execute()
            st.success("Rekap absensi berhasil disimpan!")

def menu_tambah_akun():
    st.header("Manajemen Akun Admin")
    with st.form("form_akun"):
        col1, col2 = st.columns(2)
        nama = col1.text_input("Nama Admin / Sekolah")
        username = col2.text_input("Username Login")
        unit_kerja = col1.text_input("Unit Kerja (Misal: SMAN 1 Makassar)")
        role = col2.selectbox("Jenis Akun", ["admin_sekolah", "admin_cabdis"])
        password = st.text_input("Password", type="password")
        
        submit_akun = st.form_submit_button("Buat Akun")
        if submit_akun:
            data_akun = {"nama": nama, "username": username, "unit_kerja": unit_kerja, "role": role, "password": password}
            supabase.table("users").insert(data_akun).execute()
            st.success("Akun berhasil dibuat!")
            st.rerun()

    st.subheader("Daftar Akun Sistem")
    res_akun = supabase.table("users").select("id, nama, username, unit_kerja, role").execute()
    if res_akun.data:
        st.dataframe(pd.DataFrame(res_akun.data), use_container_width=True)

if not st.session_state.logged_in:
    login_page()
else:
    with st.sidebar:
        st.title("Menu Navigasi")
        st.write(f"👋 Halo, {st.session_state.nama}")
        st.write(f"🏢 {st.session_state.unit_kerja}")
        st.divider()
        
        menu_options = []
        if st.session_state.role == 'admin_cabdis':
            menu_options = [
                "Dashboard", "Data Indisipliner PNS", "Data Indisipliner PPPK", "Tambah Akun Admin"
            ]
        elif st.session_state.role == 'admin_sekolah':
            menu_options = [
                "Data Pegawai", "Input Rekap PNS", "Input Rekap PPPK", 
                "Data Indisipliner PNS", "Data Indisipliner PPPK"
            ]
            
        pilihan = st.radio("Pilih Menu", menu_options)
        
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.rerun()

    if pilihan == "Dashboard": menu_dashboard()
    elif pilihan == "Data Pegawai": menu_data_pegawai()
    elif pilihan == "Input Rekap PNS": menu_input_absen("PNS")
    elif pilihan == "Input Rekap PPPK": menu_input_absen("PPPK")
    elif pilihan == "Tambah Akun Admin": menu_tambah_akun()
    elif pilihan == "Data Indisipliner PNS": 
        st.header("Data Indisipliner PNS")
        st.write("*Tabel pengurutan akan segera dihubungkan dengan database.*")
    elif pilihan == "Data Indisipliner PPPK": 
        st.header("Data Indisipliner PPPK")
        st.write("*Tabel pengurutan akan segera dihubungkan dengan database.*")
