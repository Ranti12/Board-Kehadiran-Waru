import io
import base64

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image
import pandas as pd
from datetime import date

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

EMPLOYEES_SHEET = "Employees"
ATTENDANCE_SHEET = "Attendance"

STATUS_CYCLE = ["belum", "hijau", "merah", "kuning"]  # urutan saat tombol diklik berulang
STATUS_ICON = {"belum": "⚪", "hijau": "🟢", "merah": "🔴", "kuning": "🟡"}
STATUS_LABEL = {
    "belum": "Belum diisi",
    "hijau": "Tepat waktu (\u2264 08.00)",
    "merah": "Telat (> 08.00)",
    "kuning": "Tidak hadir (sakit/cuti/SPD/izin)",
}
STATUS_COLORS = {"hijau": "#2F9E56", "merah": "#E14B3F", "kuning": "#DE9A1F", "belum": "#C9C7BF"}

DEFAULT_DIVISION_ORDER = "Service, Marketing, Admin, Part"

# Nama divisi lama -> nama baru (biar data lama di Sheets otomatis ikut berubah
# tanpa perlu edit manual kolom "division" satu per satu)
DIVISION_RENAME_MAP = {
    "Sales": "Marketing",
}


def next_status(current):
    idx = STATUS_CYCLE.index(current)
    return STATUS_CYCLE[(idx + 1) % len(STATUS_CYCLE)]


# ---------- Google Sheets connection ----------

def get_credentials():
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return Credentials.from_service_account_file("credentials.json", scopes=SCOPES)


@st.cache_resource
def get_client():
    return gspread.authorize(get_credentials())


# Batas aman panjang karakter per sel Google Sheets adalah 50.000 karakter.
# Dikasih ruang aman di bawahnya biar gak mepet.
MAX_DATA_URI_CHARS = 45000


def process_uploaded_photo(uploaded_file):
    """Kompres & resize foto yang diupload lewat st.file_uploader, lalu simpan
    langsung sebagai data URI (base64) di kolom photo_url pada Google Sheets.
    Tidak perlu Google Drive sama sekali -> tidak ada masalah kuota penyimpanan
    service account.
    """
    img = Image.open(uploaded_file)
    img = img.convert("RGB")

    size = 220
    quality = 75
    for _ in range(6):
        resized = img.copy()
        resized.thumbnail((size, size))
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=quality, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        data_uri = f"data:image/jpeg;base64,{b64}"
        if len(data_uri) <= MAX_DATA_URI_CHARS:
            return data_uri
        # kalau masih kepanjangan, perkecil ukuran & kualitasnya, coba lagi
        size = int(size * 0.8)
        quality = max(35, quality - 10)

    raise ValueError(
        "Foto masih terlalu besar walau sudah dikompres habis-habisan. "
        "Coba pakai foto lain (ukuran file asli lebih kecil)."
    )


@st.cache_resource
def get_spreadsheet():
    spreadsheet_id = st.secrets.get("SPREADSHEET_ID")
    if not spreadsheet_id:
        st.error(
            "SPREADSHEET_ID belum diisi. Tambahkan di .streamlit/secrets.toml "
            "(lihat README.md untuk caranya)."
        )
        st.stop()
    return get_client().open_by_key(spreadsheet_id)


def get_worksheets():
    ss = get_spreadsheet()
    try:
        ws_emp = ss.worksheet(EMPLOYEES_SHEET)
    except gspread.WorksheetNotFound:
        ws_emp = ss.add_worksheet(title=EMPLOYEES_SHEET, rows=300, cols=4)
        ws_emp.append_row(["id", "name", "photo_url", "division"])
    try:
        ws_att = ss.worksheet(ATTENDANCE_SHEET)
    except gspread.WorksheetNotFound:
        ws_att = ss.add_worksheet(title=ATTENDANCE_SHEET, rows=3000, cols=3)
        ws_att.append_row(["employee_id", "date", "status"])
    return ws_emp, ws_att


# ---------- Placeholder photo ----------

def placeholder_photo_url(emp_id):
    idx = (int(emp_id) % 70) + 1
    return f"https://i.pravatar.cc/300?img={idx}"


# ---------- Data access ----------

def load_employees_df():
    ws_emp, _ = get_worksheets()
    records = ws_emp.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=["id", "name", "photo_url", "division"])
    for col in ["photo_url", "division"]:
        if col not in df.columns:
            df[col] = ""
    df["division"] = df["division"].replace("", "Lainnya").fillna("Lainnya")
    df["division"] = df["division"].replace(DIVISION_RENAME_MAP)
    return df


def add_employee(name, photo_url="", division="Lainnya"):
    ws_emp, _ = get_worksheets()
    df = load_employees_df()
    new_id = int(df["id"].max()) + 1 if not df.empty else 1
    ws_emp.append_row([new_id, name, photo_url, division or "Lainnya"])
    return new_id


def update_employee_name(emp_id, new_name):
    ws_emp, _ = get_worksheets()
    cell = ws_emp.find(str(emp_id), in_column=1)
    if cell:
        ws_emp.update_cell(cell.row, 2, new_name)


def update_employee_photo(emp_id, photo_url):
    ws_emp, _ = get_worksheets()
    cell = ws_emp.find(str(emp_id), in_column=1)
    if cell:
        ws_emp.update_cell(cell.row, 3, photo_url)


def delete_employee(emp_id):
    ws_emp, ws_att = get_worksheets()
    cell = ws_emp.find(str(emp_id), in_column=1)
    if cell:
        ws_emp.delete_rows(cell.row)
    records = ws_att.get_all_records()
    rows_to_delete = [i + 2 for i, r in enumerate(records) if str(r["employee_id"]) == str(emp_id)]
    for row in sorted(rows_to_delete, reverse=True):
        ws_att.delete_rows(row)


def load_attendance_for_date(date_str):
    _, ws_att = get_worksheets()
    records = ws_att.get_all_records()
    return {str(r["employee_id"]): r["status"] for r in records if str(r["date"]) == date_str}


def set_attendance(emp_id, date_str, status):
    _, ws_att = get_worksheets()
    records = ws_att.get_all_records()
    row_idx = None
    for i, r in enumerate(records):
        if str(r["employee_id"]) == str(emp_id) and str(r["date"]) == date_str:
            row_idx = i + 2
            break
    if status == "belum":
        if row_idx:
            ws_att.delete_rows(row_idx)
    else:
        if row_idx:
            ws_att.update_cell(row_idx, 3, status)
        else:
            ws_att.append_row([emp_id, date_str, status])


# ---------- UI ----------

st.set_page_config(page_title="Board Kehadiran Karyawan", page_icon="\U0001F5C2\uFE0F", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #FAFAF8; }
    .board-title { text-align: center; }
    .board-title h1 {
        font-family: 'Trebuchet MS', sans-serif; font-weight: 800;
        margin-bottom: 0; letter-spacing: 0.02em;
    }
    .board-title h3 {
        font-family: 'Trebuchet MS', sans-serif; font-weight: 600;
        margin-top: 0; color: #444; letter-spacing: 0.03em;
    }
    .legend-box {
        display: flex; gap: 22px; justify-content: center; flex-wrap: wrap;
        margin: 6px 0 18px 0; font-size: 13px;
    }
    .legend-item { display: flex; align-items: center; gap: 6px; }
    .legend-dot { width: 14px; height: 14px; border-radius: 50%; display: inline-block; }
    .division-header {
        text-align: center; font-weight: 700; font-size: 15px;
        border-bottom: 2px solid #333; padding-bottom: 6px; margin-bottom: 10px;
        text-transform: uppercase; letter-spacing: 0.05em;
    }
    .emp-row-name { font-size: 11.5px; color: #333; line-height: 1.2; }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Pengaturan Board")
    board_title = st.text_input("Judul board", value="KEHADIRAN KARYAWAN")
    board_subtitle = st.text_input("Sub-judul (nama cabang)", value="CABANG WARU")
    division_order_raw = st.text_input("Urutan divisi (pisahkan koma)", value=DEFAULT_DIVISION_ORDER)
    show_names = st.checkbox("Tampilkan nama di kartu", value=True)

    st.divider()
    st.header("Kelola Karyawan")
    known_divisions = [d.strip() for d in division_order_raw.split(",") if d.strip()]
    with st.form("add_employee_form", clear_on_submit=True):
        new_name = st.text_input("Nama / label (mis. A, B, C jika belum tahu nama aslinya)")
        new_division = st.selectbox("Divisi", options=known_divisions + ["Lainnya"])
        new_photo_file = st.file_uploader(
            "Upload foto (opsional)", type=["jpg", "jpeg", "png", "webp"]
        )
        new_photo_url = st.text_input(
            "Atau isi URL foto (kosongkan kalau upload file di atas / belum ada)",
            help="Kalau dua-duanya kosong, otomatis dikasih foto sementara (placeholder).",
        )
        submitted = st.form_submit_button("+ Tambah")
        if submitted and new_name.strip():
            photo_url = new_photo_url.strip()
            if new_photo_file is not None:
                try:
                    with st.spinner("Memproses foto..."):
                        photo_url = process_uploaded_photo(new_photo_file)
                except Exception as e:
                    st.error(f"Gagal memproses foto: {e}")
                    st.stop()
            add_employee(new_name.strip(), photo_url, new_division)
            st.rerun()

    st.divider()
    employees_df_sidebar = load_employees_df()
    if not employees_df_sidebar.empty:
        st.caption("Ubah nama / foto / hapus karyawan")
        for _, row in employees_df_sidebar.iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            edited_name = c1.text_input(
                "Nama",
                value=row["name"],
                key=f"name_{row['id']}",
                label_visibility="collapsed",
            )
            if c2.button("\U0001F4BE", key=f"save_{row['id']}", help="Simpan nama baru"):
                if edited_name.strip() and edited_name.strip() != row["name"]:
                    update_employee_name(row["id"], edited_name.strip())
                    st.rerun()
            if c3.button("\U0001F5D1\uFE0F", key=f"del_{row['id']}", help="Hapus karyawan"):
                delete_employee(row["id"])
                st.rerun()

            with st.expander(f"\U0001F4F7 Ganti foto - {row['name']}"):
                replacement_photo = st.file_uploader(
                    "Foto baru",
                    type=["jpg", "jpeg", "png", "webp"],
                    key=f"photofile_{row['id']}",
                )
                if replacement_photo is not None and st.button(
                    "Simpan foto ini", key=f"savephoto_{row['id']}"
                ):
                    try:
                        with st.spinner("Memproses foto..."):
                            new_photo_url = process_uploaded_photo(replacement_photo)
                        update_employee_photo(row["id"], new_photo_url)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal memproses foto: {e}")

    st.divider()
    if st.button("\U0001F504 Refresh data dari Sheets"):
        st.rerun()

# --- Header ---
st.markdown(
    f"""
    <div class="board-title">
        <h1>{board_title}</h1>
        <h3>{board_subtitle}</h3>
    </div>
    <div class="legend-box">
        <span class="legend-item"><span class="legend-dot" style="background:{STATUS_COLORS['merah']}"></span> &gt; 08.00 (Telat)</span>
        <span class="legend-item"><span class="legend-dot" style="background:{STATUS_COLORS['hijau']}"></span> &le; 08.00 (Tepat waktu)</span>
        <span class="legend-item"><span class="legend-dot" style="background:{STATUS_COLORS['kuning']}"></span> Tidak hadir (sakit, cuti, SPD, izin)</span>
    </div>
    """,
    unsafe_allow_html=True,
)

selected_date = st.date_input("Tanggal", value=date.today())
date_str = selected_date.isoformat()

employees_df = load_employees_df()
attendance_map = load_attendance_for_date(date_str)

# --- Summary ---
counts = {"hijau": 0, "merah": 0, "kuning": 0, "belum": 0}
for _, row in employees_df.iterrows():
    status = attendance_map.get(str(row["id"]), "belum")
    counts[status] += 1

c1, c2, c3, c4 = st.columns(4)
c1.metric("\U0001F7E2 Tepat waktu", counts["hijau"])
c2.metric("\U0001F534 Telat", counts["merah"])
c3.metric("\U0001F7E1 Tidak hadir", counts["kuning"])
c4.metric("\u26AA Belum diisi", counts["belum"])

st.divider()

if employees_df.empty:
    st.info("Belum ada karyawan. Tambahkan lewat panel di sebelah kiri.")
else:
    # urutan divisi: sesuai pengaturan sidebar dulu, sisanya (yang ada di data tapi belum
    # terdaftar di urutan) ditambahkan di akhir
    data_divisions = list(employees_df["division"].unique())
    ordered_divisions = [d for d in known_divisions if d in data_divisions]
    ordered_divisions += [d for d in data_divisions if d not in ordered_divisions]

    division_cols = st.columns(len(ordered_divisions))

    for div_col, division in zip(division_cols, ordered_divisions):
        with div_col:
            st.markdown(f'<div class="division-header">{division}</div>', unsafe_allow_html=True)
            div_employees = employees_df[employees_df["division"] == division]

            for _, emp in div_employees.iterrows():
                current_status = attendance_map.get(str(emp["id"]), "belum")
                photo = emp["photo_url"] if emp.get("photo_url") else placeholder_photo_url(emp["id"])
                ring = STATUS_COLORS[current_status]

                row_photo, row_info = st.columns([1, 2])
                with row_photo:
                    st.markdown(
                        f'<img src="{photo}" style="width:44px;height:44px;object-fit:cover;'
                        f'border-radius:50%;border:2.5px solid {ring};">',
                        unsafe_allow_html=True,
                    )
                with row_info:
                    if show_names:
                        st.markdown(f'<div class="emp-row-name">{emp["name"]}</div>', unsafe_allow_html=True)
                    chosen_label = st.selectbox(
                        "Status",
                        options=STATUS_CYCLE,
                        index=STATUS_CYCLE.index(current_status),
                        format_func=lambda s: f"{STATUS_ICON[s]} {STATUS_LABEL[s]}",
                        key=f"sel_{emp['id']}_{date_str}",
                        label_visibility="collapsed",
                    )
                    if chosen_label != current_status:
                        set_attendance(emp["id"], date_str, chosen_label)
                        st.rerun()

st.caption("Pilih status lewat dropdown di bawah tiap foto. Data tersimpan otomatis ke Google Sheets.")
